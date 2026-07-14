"""Tests du bus d'événements métier work.*."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel

from app.agent.loop import AgentLoop
from app.agent.tools import ToolDeps, build_agent
from app.agent.work_events import capability_label, work_id_for_turn
from app.audit import read_audit, resolve_app_data_dir
from app.plugins.workproba_browser import manifest as browser_manifest
from app.schemas import (
    AgentTurnRequest,
    DoneEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
    WorkCompletedEvent,
    WorkContributionEvent,
    WorkStartedEvent,
)
from app.sandbox.runner import SandboxRunner

from conftest import FakeProjectClient


def _make_request(
    message: str = "lire",
    *,
    workspace_data_dir: str | None = None,
    audit_enabled: bool = False,
) -> AgentTurnRequest:
    return AgentTurnRequest(
        tenant_id="t",
        project_id="p",
        session_id="s",
        message=message,
        documents=[],
        workspace_data_dir=workspace_data_dir,
        audit_enabled=audit_enabled,
    )


async def _run(loop: AgentLoop, request: AgentTurnRequest, *, turn_id: str = "turn-test") -> list[Any]:
    return [event async for event in loop.run_turn(request, turn_id=turn_id)]


def _event_sse_types(events: list[Any]) -> list[str]:
    return [getattr(event, "type", type(event).__name__) for event in events]


def test_work_id_for_turn_is_turn_id() -> None:
    turn_id = "turn-abc-123"
    assert work_id_for_turn(turn_id) == turn_id
    assert work_id_for_turn(turn_id) == work_id_for_turn(turn_id)


@pytest.mark.parametrize(
    ("tool_name", "locale", "expected_kind", "expected_label_key"),
    [
        ("list_files", "fr", "capability", "work.capability.document_analysis"),
        ("search_kb", "fr", "capability", "work.capability.document_analysis"),
        ("read_document", "fr", "capability", "work.capability.document_analysis"),
        ("recall_project_sessions", "fr", "capability", "work.capability.document_analysis"),
        ("web_search", "en", "capability", "work.capability.web_search"),
        ("browser_navigate", "fr", "capability", "work.capability.web_browsing"),
        ("browser_click", "en", "capability", "work.capability.web_browsing"),
        ("write_docx", "fr", "capability", "work.capability.office_generation"),
        ("write_xlsx", "en", "capability", "work.capability.office_generation"),
        ("write_pdf", "fr", "capability", "work.capability.office_generation"),
        ("generate_document", "en", "capability", "work.capability.office_generation"),
        ("run_code", "fr", "capability", "work.capability.code_execution"),
        ("publish_artifact", "en", "capability", "work.capability.publishing"),
        ("create_project", "fr", "capability", "work.capability.publishing"),
        ("list_projects", "en", "capability", "work.capability.publishing"),
        ("sync_to_cloud", "fr", "capability", "work.capability.publishing"),
        ("ask_personas", "en", "perspective", "work.perspective.business"),
        ("simulate_meeting", "fr", "perspective", "work.perspective.business"),
        ("propose_plan", "en", "capability", "work.capability.planning"),
        ("remember", "fr", "capability", "work.capability.planning"),
        ("fake_plugin_tool", "en", "capability", "work.capability.generic"),
    ],
)
def test_capability_label_core_and_unknown_tools(
    tool_name: str,
    locale: str,
    expected_kind: str,
    expected_label_key: str,
) -> None:
    from app.i18n import t

    kind, label = capability_label(tool_name, locale)
    assert kind == expected_kind
    assert label == t(locale, expected_label_key)


def test_capability_label_covers_all_browser_tools() -> None:
    for tool_name in browser_manifest.TOOLS:
        kind, label = capability_label(tool_name, "fr")
        assert kind == "capability"
        assert label


def _new_loop(client: FakeProjectClient, agent: Any | None = None) -> AgentLoop:
    built_agent = agent or build_agent(TestModel(seed=0, call_tools=["read_document"]))
    return AgentLoop(
        agent=built_agent,
        project_client=client,
        sandbox_runner=SandboxRunner(timeout_seconds=10),
        max_iterations=6,
    )


def _agent_with_fake_plugin_tool() -> Any:
    agent = build_agent(TestModel(seed=1, call_tools=["fake_plugin_tool"]))

    @agent.tool
    async def fake_plugin_tool(ctx: RunContext[ToolDeps]) -> dict[str, str]:
        return {"ok": True}

    return agent


@pytest.mark.asyncio
async def test_agent_loop_emits_work_events_with_tool_sse(fake_project_client: FakeProjectClient) -> None:
    fake_project_client._documents = {"a": "contenu du document A"}
    loop = _new_loop(fake_project_client)
    turn_id = "turn-work-events"
    events = await _run(loop, _make_request(), turn_id=turn_id)

    sse_types = _event_sse_types(events)
    assert sse_types[0] == "work_started"
    assert isinstance(events[0], WorkStartedEvent)
    assert events[0].work_id == turn_id

    assert ToolCallStartEvent.__name__ in [type(e).__name__ for e in events]
    assert ToolCallResultEvent.__name__ in [type(e).__name__ for e in events]

    contributions = [e for e in events if isinstance(e, WorkContributionEvent)]
    assert len(contributions) >= 2
    started = [e for e in contributions if e.status == "started"]
    completed = [e for e in contributions if e.status == "completed"]
    assert started
    assert completed
    assert started[0].contribution_id == completed[0].contribution_id
    assert started[0].label

    work_completed_idx = next(
        i for i, event in enumerate(events) if isinstance(event, WorkCompletedEvent)
    )
    assert sse_types[work_completed_idx] == "work_completed"
    assert isinstance(events[-1], DoneEvent)
    assert work_completed_idx < len(events) - 1


@pytest.mark.asyncio
async def test_turn_prompt_audit_contains_work_id(
    fake_project_client: FakeProjectClient,
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "app_data" / "spaces" / "space-1" / "project"
    workspace.mkdir(parents=True)
    fake_project_client._documents = {"a": "contenu"}

    loop = _new_loop(fake_project_client)
    turn_id = "turn-audit-work"
    await _run(
        loop,
        _make_request(workspace_data_dir=str(workspace), audit_enabled=True),
        turn_id=turn_id,
    )

    entries, total = read_audit(resolve_app_data_dir(workspace), event="turn.prompt")
    assert total == 1
    assert entries[0]["details"]["work_id"] == turn_id


@pytest.mark.asyncio
async def test_fake_plugin_tool_emits_work_contribution_with_label() -> None:
    client = FakeProjectClient(documents={})
    loop = _new_loop(client, agent=_agent_with_fake_plugin_tool())
    events = await _run(loop, _make_request("test plugin"))

    contributions = [
        e
        for e in events
        if isinstance(e, WorkContributionEvent)
        and e.status == "started"
    ]
    fake_started = [e for e in contributions if e.label]
    assert fake_started
    assert fake_started[0].kind == "capability"
    assert fake_started[0].summary
