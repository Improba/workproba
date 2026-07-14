"""Classification déterministe des effets approuvables par outil agent."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.i18n import t

EffectType = Literal[
    "create",
    "modify",
    "delete",
    "send",
    "publish",
    "network_access",
    "code_execute",
    "external_send",
]

_NO_EFFECT_TOOLS = frozenset(
    {
        "list_files",
        "search_kb",
        "read_document",
        "recall_project_sessions",
        "remember",
        "propose_plan",
        "ask_personas",
        "simulate_meeting",
        "create_project",
        "list_projects",
    }
)

_WRITE_TOOLS = frozenset(
    {"write_docx", "write_xlsx", "write_pdf", "generate_document"}
)

_BROWSER_TOOLS = frozenset(
    {
        "browser_navigate",
        "browser_click",
        "browser_extract",
        "browser_type",
        "browser_scroll",
        "browser_press",
        "browser_back",
        "browser_forward",
    }
)


class EffectProtection(BaseModel):
    preview: bool = False
    version_before_modify: bool = False
    network_used: bool = False
    external_send: bool = False


class EffectProposal(BaseModel):
    effect: EffectType
    tool_name: str
    targets: list[str] = Field(default_factory=list)
    action: Literal["create", "modify"] = "create"
    protections: EffectProtection = Field(default_factory=EffectProtection)
    human_summary: str = ""
    proposed_path: str = ""


def _normalize_relative_path(file_path: str) -> str:
    normalized = file_path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _resolve_write_action(
    project_root: Path | None,
    name: str,
) -> tuple[str, Literal["create", "modify"]]:
    """Même logique que ``tools._write_action`` (évite l'import circulaire)."""
    proposed_path = _normalize_relative_path(name)
    if project_root is None:
        return proposed_path, "create"
    target = (project_root / proposed_path).resolve()
    if target.is_file():
        return proposed_path, "modify"
    return proposed_path, "create"


def _coerce_project_root(value: Any) -> Path | None:
    if value is None:
        return None
    if isinstance(value, Path):
        return value
    if isinstance(value, str) and value.strip():
        return Path(value)
    return None


def protections_to_dict(protections: EffectProtection) -> dict[str, bool]:
    return {
        "preview": protections.preview,
        "version_before_modify": protections.version_before_modify,
        "network_used": protections.network_used,
        "external_send": protections.external_send,
    }


def effect_label(effect: EffectType, locale: str) -> str:
    """Libellé localisé d'un type d'effet."""
    return t(locale, f"effect.{effect}")


def classify_effect(
    tool_name: str,
    args: dict[str, Any],
    *,
    permissions_network: bool,
) -> EffectProposal | None:
    """Retourne une proposition d'effet ou None si l'outil n'est pas approuvable.

    Les outils inconnus (plugins futurs) retournent None par défaut : approche
    conservatrice, ils ne sont pas auto-gated tant qu'ils ne sont pas mappés.

    ``permissions_network`` est accepté pour homogénéité d'appel ; le blocage réseau
    reste en amont (permissions), pas dans cette classification.
    """
    _ = permissions_network

    if tool_name in _WRITE_TOOLS:
        name = str(args.get("name") or args.get("path") or "")
        project_root = _coerce_project_root(args.get("project_root"))
        proposed_path, action = _resolve_write_action(project_root, name)
        basename = os.path.basename(proposed_path) or name
        return EffectProposal(
            effect=action,
            tool_name=tool_name,
            targets=[basename] if basename else [],
            action=action,
            protections=EffectProtection(
                preview=True,
                version_before_modify=action == "modify",
                network_used=False,
                external_send=False,
            ),
            proposed_path=proposed_path,
        )

    if tool_name == "publish_artifact":
        artefact_name = str(args.get("name") or "")
        project_id = str(args.get("project_id") or "")
        project = str(args.get("project") or project_id)
        targets = [value for value in (artefact_name, project) if value]
        proposed_path = (
            f"artefacts/{project_id}/{artefact_name}" if project_id and artefact_name else ""
        )
        return EffectProposal(
            effect="publish",
            tool_name=tool_name,
            targets=targets,
            action="create",
            protections=EffectProtection(
                preview=False,
                version_before_modify=False,
                network_used=False,
                external_send=False,
            ),
            proposed_path=proposed_path,
        )

    if tool_name == "sync_to_cloud":
        project_id = str(args.get("project_id") or "")
        return EffectProposal(
            effect="external_send",
            tool_name=tool_name,
            targets=[project_id] if project_id else [],
            action="create",
            protections=EffectProtection(
                network_used=True,
                external_send=True,
            ),
        )

    if tool_name == "web_search":
        query = str(args.get("query") or "")
        short_query = query[:80] if query else ""
        return EffectProposal(
            effect="network_access",
            tool_name=tool_name,
            targets=[short_query] if short_query else [],
            action="create",
            protections=EffectProtection(network_used=True),
        )

    if tool_name in _BROWSER_TOOLS or tool_name.startswith("browser_"):
        return EffectProposal(
            effect="network_access",
            tool_name=tool_name,
            targets=[],
            action="create",
            protections=EffectProtection(network_used=True),
        )

    if tool_name == "run_code":
        return EffectProposal(
            effect="code_execute",
            tool_name=tool_name,
            targets=[],
            action="create",
            protections=EffectProtection(),
        )

    if tool_name in _NO_EFFECT_TOOLS:
        return None

    return None
