"""Tests corrélation audit turn_id / work_id / session_id."""

from __future__ import annotations

from app.agent.work_events import audit_details_with_work_id
from app.audit import audit_correlation, merge_audit_details


def test_audit_correlation_includes_all_ids() -> None:
    payload = audit_correlation(
        turn_id="turn-1",
        work_id="turn-1",
        session_id="sess-1",
    )
    assert payload == {
        "turn_id": "turn-1",
        "work_id": "turn-1",
        "session_id": "sess-1",
    }


def test_merge_audit_details_does_not_override_existing() -> None:
    merged = merge_audit_details(
        {"turn_id": "existing-turn", "tool_name": "write_docx"},
        turn_id="new-turn",
        work_id="work-1",
        session_id="sess-1",
    )
    assert merged["turn_id"] == "existing-turn"
    assert merged["work_id"] == "work-1"
    assert merged["session_id"] == "sess-1"
    assert merged["tool_name"] == "write_docx"


def test_audit_details_with_work_id_adds_optional_turn_and_session() -> None:
    details = audit_details_with_work_id(
        {"effect": "write"},
        "turn-42",
        turn_id="turn-42",
        session_id="sess-9",
    )
    assert details["work_id"] == "turn-42"
    assert details["turn_id"] == "turn-42"
    assert details["session_id"] == "sess-9"
