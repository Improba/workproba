"""Bus d'événements métier work.* (additif, découplé de l'UI outil par outil)."""

from __future__ import annotations

from typing import Any, Literal

from app.i18n import t
from app.schemas import (
    WorkCompletedEvent,
    WorkContributionEvent,
    WorkFailedEvent,
    WorkStartedEvent,
)

WorkKind = Literal["capability", "perspective", "control"]
ContributionStatus = Literal["started", "completed", "failed", "cancelled"]
WorkPhase = Literal["started", "contribution", "completed", "failed"]

_DOCUMENT_TOOLS = frozenset(
    {"list_files", "search_kb", "read_document", "recall_project_sessions"}
)
_OFFICE_TOOLS = frozenset(
    {"write_docx", "write_xlsx", "write_pptx", "write_pdf", "generate_document"}
)
_PUBLISHING_TOOLS = frozenset(
    {"publish_artifact", "create_project", "list_projects", "sync_to_cloud"}
)
_PERSPECTIVE_TOOLS = frozenset({"ask_personas", "simulate_meeting"})
_PLANNING_TOOLS = frozenset({"propose_plan", "remember"})


def work_id_for_turn(turn_id: str) -> str:
    """Retourne l'identifiant de travail pour un tour agent.

    Un work = un tour pour l'instant. Point d'extension pour un work_id partagé
    par un plan multi-étapes ultérieur.
    """
    return turn_id


def capability_label(tool_name: str, locale: str) -> tuple[WorkKind, str]:
    """Mappe un outil vers un kind métier et un libellé coarse localisé."""
    if tool_name in _DOCUMENT_TOOLS:
        return "capability", t(locale, "work.capability.document_analysis")
    if tool_name == "web_search":
        return "capability", t(locale, "work.capability.web_search")
    if tool_name.startswith("browser_"):
        return "capability", t(locale, "work.capability.web_browsing")
    if tool_name in _OFFICE_TOOLS:
        return "capability", t(locale, "work.capability.office_generation")
    if tool_name == "run_code":
        return "capability", t(locale, "work.capability.code_execution")
    if tool_name in _PUBLISHING_TOOLS:
        return "capability", t(locale, "work.capability.publishing")
    if tool_name in _PERSPECTIVE_TOOLS:
        return "perspective", t(locale, "work.perspective.business")
    if tool_name in _PLANNING_TOOLS:
        return "capability", t(locale, "work.capability.planning")
    return "capability", t(locale, "work.capability.generic")


def audit_details_with_work_id(
    details: dict[str, Any],
    work_id: str | None,
    *,
    turn_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Ajoute work_id (et corrélation optionnelle) dans details d'audit."""
    merged = dict(details)
    if work_id:
        merged.setdefault("work_id", work_id)
    if turn_id:
        merged.setdefault("turn_id", turn_id)
    if session_id:
        merged.setdefault("session_id", session_id)
    return merged


def derive_work_event(
    *,
    phase: WorkPhase,
    work_id: str,
    locale: str = "fr",
    objective: str = "",
    tool_name: str = "",
    contribution_id: str = "",
    contribution_status: ContributionStatus = "started",
    summary: str = "",
    turn_summary: str = "",
    code: str = "",
    message: str = "",
) -> (
    WorkStartedEvent
    | WorkContributionEvent
    | WorkCompletedEvent
    | WorkFailedEvent
):
    """Produit un événement work.* à partir d'une phase du flux agent."""
    if phase == "started":
        return WorkStartedEvent(work_id=work_id, objective=objective)
    if phase == "contribution":
        kind, label = capability_label(tool_name, locale)
        return WorkContributionEvent(
            work_id=work_id,
            contribution_id=contribution_id,
            kind=kind,
            label=label,
            status=contribution_status,
            summary=summary,
        )
    if phase == "completed":
        return WorkCompletedEvent(work_id=work_id, summary=turn_summary)
    return WorkFailedEvent(work_id=work_id, code=code, message=message)
