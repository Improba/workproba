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
    headline: str = ""
    protection_labels: list[str] = Field(default_factory=list)


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


_NETWORK_EFFECTS = frozenset({"network_access", "external_send"})


def _join_targets(targets: list[str]) -> str:
    return ", ".join(value for value in targets if value)


def effect_headline(proposal: EffectProposal, locale: str) -> str:
    """Phrase localisée orientée effet pour la carte de confirmation."""
    effect = proposal.effect
    targets = _join_targets(proposal.targets)

    if effect == "publish":
        artefact = proposal.targets[0] if proposal.targets else ""
        project = proposal.targets[1] if len(proposal.targets) > 1 else ""
        return t(
            locale,
            "effect.headline.publish",
            artefact=artefact,
            project=project,
        )
    if effect == "network_access":
        return t(locale, "effect.headline.network_access", targets=targets)
    if effect == "code_execute":
        return t(locale, "effect.headline.code_execute")
    if effect == "external_send":
        return t(locale, "effect.headline.external_send", targets=targets)

    label = effect_label(effect, locale)
    return t(locale, "effect.headline.default", effect=label, targets=targets)


def protection_labels(proposal: EffectProposal, locale: str) -> list[str]:
    """Phrases localisées décrivant les protections actives ou absentes."""
    labels: list[str] = []
    protections = proposal.protections

    if protections.preview:
        labels.append(t(locale, "effect.protection.preview"))
    if protections.version_before_modify:
        labels.append(t(locale, "effect.protection.version_before_modify"))
    if not protections.network_used and proposal.effect not in _NETWORK_EFFECTS:
        labels.append(t(locale, "effect.protection.no_network"))
    if not protections.external_send:
        labels.append(t(locale, "effect.protection.no_external_send"))

    return labels


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

    if tool_name == "sync_from_cloud":
        project_id = str(args.get("project_id") or "")
        return EffectProposal(
            effect="modify",
            tool_name=tool_name,
            targets=[project_id] if project_id else [],
            action="modify",
            protections=EffectProtection(
                network_used=True,
            ),
        )

    if tool_name == "sync_managed_regards":
        org_id = str(args.get("org_id") or "")
        return EffectProposal(
            effect="modify",
            tool_name=tool_name,
            targets=[org_id] if org_id else [],
            action="modify",
            protections=EffectProtection(
                network_used=True,
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
