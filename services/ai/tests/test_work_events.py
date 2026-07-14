"""Tests du bus d'événements métier work.*."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import APITimeoutError
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel

import app.auth as authmod
import app.main as mainmod
from app.agent.loop import AgentLoop
from app.agent.tools import ToolDeps, build_agent
from app.agent.work_events import capability_label, derive_work_event, work_id_for_turn
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

INTERNAL_HEADERS = {"X-Internal-Secret": "desktop-dev-secret"}


def _httpx_request() -> httpx.Request:
    return httpx.Request("POST", "http://example.test/v1/chat/completions")


def _sse_events(resp: Any) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    event_type: str | None = None
    data: str | None = None
    for line in resp.iter_lines():
        if line.startswith("event:"):
            event_type = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data = line[len("data:") :].strip()
        elif line == "" and event_type and data:
            events.append((event_type, json.loads(data)))
            event_type = None
            data = None
    if event_type and data:
        events.append((event_type, json.loads(data)))
    return events


def _turn_payload(tmp_path: Path, **overrides: Any) -> dict[str, Any]:
    payload = {
        "tenant_id": "t",
        "project_id": str(tmp_path),
        "project_path": str(tmp_path),
        "session_id": "sess-work-events",
        "message": "hello",
        "history": [],
        "documents": [],
    }
    payload.update(overrides)
    return payload


def _provider_set_with_fallback() -> dict[str, Any]:
    return {
        "id": "test-fallback",
        "chat": {
            "provider": "mistral",
            "model": "mistral-small-latest",
            "api_key": "primary-key",
        },
        "chat_fallback": {
            "provider": "ollama",
            "model": "llama3.2",
        },
    }


def _assert_work_failed_before_error(
    events: list[tuple[str, dict[str, Any]]],
    *,
    code: str,
    turn_id: str,
) -> None:
    event_types = [event_type for event_type, _data in events]
    failed_indices = [i for i, event_type in enumerate(event_types) if event_type == "work_failed"]
    error_indices = [i for i, event_type in enumerate(event_types) if event_type == "error"]
    assert failed_indices, f"work_failed manquant pour code={code}"
    assert error_indices, f"error manquant pour code={code}"
    failed_idx = next(
        i
        for i in failed_indices
        if events[i][1].get("code") == code
    )
    error_idx = next(
        i
        for i in error_indices
        if events[i][1].get("code") == code
    )
    assert failed_idx < error_idx
    failed_data = events[failed_idx][1]
    error_data = events[error_idx][1]
    assert failed_data["work_id"] == turn_id
    assert failed_data["code"] == code
    assert error_data["code"] == code
    assert failed_data["message"] == error_data["message"]
    assert event_types.count("work_completed") == 0


@pytest.fixture(autouse=True)
def _patch_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)


@pytest.fixture(autouse=True)
def _patch_build_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mainmod,
        "build_model",
        lambda config: TestModel(seed=0, call_tools=[]),
    )


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


def test_derive_work_event_accepts_cancelled_status() -> None:
    event = derive_work_event(
        phase="contribution",
        work_id="turn-1",
        locale="fr",
        tool_name="write_docx",
        contribution_id="tc-1",
        contribution_status="cancelled",
        summary="Action annulée",
    )
    assert isinstance(event, WorkContributionEvent)
    assert event.status == "cancelled"


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


def test_agent_turn_timeout_emits_work_failed_before_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SlowLoop:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def run_turn(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
            await asyncio.sleep(5)
            if False:
                yield

    monkeypatch.setattr(mainmod, "AgentLoop", SlowLoop)
    turn_id = "turn-timeout-work-failed"

    with TestClient(mainmod.app) as client:
        client.app.state.settings.turn_timeout_seconds = 1
        with client.stream(
            "POST",
            "/agent/turn",
            json=_turn_payload(tmp_path, session_id="sess-timeout-wf", turn_id=turn_id),
            headers=INTERNAL_HEADERS,
        ) as resp:
            events = _sse_events(resp)

    _assert_work_failed_before_error(events, code="turn_timeout", turn_id=turn_id)


def test_agent_turn_provider_unavailable_emits_work_failed_before_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_stream(
        self: AgentLoop, node: Any, ctx: Any
    ) -> AsyncIterator[Any]:
        raise APITimeoutError(request=_httpx_request())
        yield  # pragma: no cover

    monkeypatch.setattr(AgentLoop, "_iter_model_stream", fail_stream)
    turn_id = "turn-provider-work-failed"

    with TestClient(mainmod.app) as client:
        with client.stream(
            "POST",
            "/agent/turn",
            json=_turn_payload(
                tmp_path,
                session_id="sess-provider-wf",
                turn_id=turn_id,
                provider_set={
                    "id": "no-fallback",
                    "chat": {
                        "provider": "mistral",
                        "model": "mistral-small-latest",
                        "api_key": "primary-key",
                    },
                },
            ),
            headers=INTERNAL_HEADERS,
        ) as resp:
            events = _sse_events(resp)

    _assert_work_failed_before_error(events, code="provider_unavailable", turn_id=turn_id)


def test_agent_turn_internal_error_emits_work_failed_before_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(_config: Any) -> Any:
        raise RuntimeError("bad llm config")

    monkeypatch.setattr(mainmod, "build_model", boom)
    turn_id = "turn-internal-work-failed"

    with TestClient(mainmod.app) as client:
        with client.stream(
            "POST",
            "/agent/turn",
            json=_turn_payload(tmp_path, session_id="sess-internal-wf", turn_id=turn_id),
            headers=INTERNAL_HEADERS,
        ) as resp:
            events = _sse_events(resp)

    _assert_work_failed_before_error(events, code="internal_error", turn_id=turn_id)


def test_agent_turn_fallback_retry_emits_single_work_started(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = AgentLoop._iter_model_stream
    call_count = {"n": 0}

    async def patched_stream(
        self: AgentLoop, node: Any, ctx: Any
    ) -> AsyncIterator[Any]:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise APITimeoutError(request=_httpx_request())
        async for event in original(self, node, ctx):
            yield event

    monkeypatch.setattr(AgentLoop, "_iter_model_stream", patched_stream)

    with TestClient(mainmod.app) as client:
        with client.stream(
            "POST",
            "/agent/turn",
            json=_turn_payload(
                tmp_path,
                session_id="sess-fallback-single-ws",
                provider_set=_provider_set_with_fallback(),
            ),
            headers=INTERNAL_HEADERS,
        ) as resp:
            events = _sse_events(resp)

    event_types = [event_type for event_type, _data in events]
    assert event_types.count("work_started") == 1
    assert "fallback" in event_types
    assert "work_completed" in event_types
    assert "work_failed" not in event_types
    assert call_count["n"] >= 2
