"""Tests de durcissement du chat backend (SSE, auth, concurrence, timeouts)."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.models.test import TestModel

import app.auth as authmod
import app.main as mainmod
from app.agent.confirmation import ConfirmationGate, confirmation_registry
from app.agent.loop import AgentLoop
from app.agent.tools import build_agent
from app.config import get_settings
from app.schemas import AgentTurnRequest, ErrorEvent
from app.sandbox.runner import SandboxRunner
from app.turn_manager import turn_manager

from conftest import FakeProjectClient
INTERNAL_HEADERS = {"X-Internal-Secret": "desktop-dev-secret"}


@pytest.fixture(autouse=True)
def _patch_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)


def _sse_events(resp: Any) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    event_type: str | None = None
    data: str | None = None
    for line in resp.iter_lines():
        if line.startswith("event:"):
            event_type = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data = line[len("data:"):].strip()
        elif line == "" and event_type and data:
            events.append((event_type, json.loads(data)))
            event_type = None
            data = None
    if event_type and data:
        events.append((event_type, json.loads(data)))
    return events


def _turn_payload(tmp_path: Any, **overrides: Any) -> dict[str, Any]:
    payload = {
        "tenant_id": "t",
        "project_id": str(tmp_path),
        "project_path": str(tmp_path),
        "session_id": "sess-hardening",
        "message": "lire",
        "history": [],
        "documents": [],
    }
    payload.update(overrides)
    return payload


async def test_generic_llm_exception_emits_internal_error_event(
    fake_project_client: FakeProjectClient,
) -> None:
    agent = build_agent(TestModel(seed=0))
    loop = AgentLoop(
        agent=agent,
        project_client=fake_project_client,
        sandbox_runner=SandboxRunner(timeout_seconds=10),
        max_iterations=6,
    )
    request = AgentTurnRequest(
        project_id="p",
        session_id="sess-err",
        message="test",
        documents=[],
    )

    async def failing_iter(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("provider network failure")
        yield  # pragma: no cover

    mock_agent = MagicMock()
    mock_agent.iter = failing_iter
    loop._agent = mock_agent  # type: ignore[method-assign]

    events = [event async for event in loop.run_turn(request, turn_id="turn-err")]
    error_events = [event for event in events if isinstance(event, ErrorEvent)]
    assert error_events
    assert error_events[-1].code == "internal_error"
    assert "interne" in error_events[-1].message.lower()


def test_agent_turn_closes_project_client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    close_calls = 0
    original_close = mainmod.LocalProjectClient.close

    async def spy_close(self: mainmod.LocalProjectClient) -> None:
        nonlocal close_calls
        close_calls += 1
        await original_close(self)

    monkeypatch.setattr(
        mainmod,
        "build_model",
        lambda config: TestModel(seed=0, call_tools=[]),
    )
    monkeypatch.setattr(mainmod.LocalProjectClient, "close", spy_close)

    with TestClient(mainmod.app) as client:
        with client.stream(
            "POST",
            "/agent/turn",
            json=_turn_payload(tmp_path, session_id="sess-close"),
            headers=INTERNAL_HEADERS,
        ) as resp:
            assert resp.status_code == 200
            list(resp.iter_lines())

    assert close_calls == 1


def test_agent_turn_without_secret_returns_401(tmp_path) -> None:
    with TestClient(mainmod.app) as client:
        resp = client.post(
            "/agent/turn",
            json=_turn_payload(tmp_path, session_id="sess-no-secret"),
        )
    assert resp.status_code == 401


def test_versions_without_secret_returns_401(tmp_path) -> None:
    with TestClient(mainmod.app) as client:
        resp = client.get(
            "/versions",
            params={
                "project_path": str(tmp_path),
                "session_id": "sess-v",
                "file_path": "f.md",
            },
        )
    assert resp.status_code == 401


def test_concurrent_turn_same_session_returns_409(tmp_path) -> None:
    session_id = "sess-concurrent"

    async def hold_turn() -> None:
        assert await turn_manager.try_acquire(session_id, "turn-held")

    asyncio.run(hold_turn())
    try:
        with TestClient(mainmod.app) as client:
            resp = client.post(
                "/agent/turn",
                json=_turn_payload(tmp_path, session_id=session_id),
                headers=INTERNAL_HEADERS,
            )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "turn_in_progress"
    finally:
        asyncio.run(turn_manager.release(session_id, "turn-held"))


def test_history_too_long_returns_422(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mainmod, "build_model", lambda config: TestModel(seed=0))
    max_messages = get_settings().max_history_messages
    history = [
        {"role": "user", "content": f"m{i}"}
        for i in range(max_messages + 1)
    ]
    with TestClient(mainmod.app) as client:
        resp = client.post(
            "/agent/turn",
            json=_turn_payload(tmp_path, session_id="sess-long", history=history),
            headers=INTERNAL_HEADERS,
        )
    assert resp.status_code == 422
    assert resp.json()["code"] == "input_too_large"


def test_turn_timeout_emits_error_event(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mainmod, "build_model", lambda config: TestModel(seed=0, call_tools=[]))

    class SlowLoop:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            # event_stream instancie AgentLoop avec agent=..., project_client=..., etc.
            pass

        async def run_turn(self, *args: Any, **kwargs: Any) -> Any:
            await asyncio.sleep(5)
            if False:
                yield

    monkeypatch.setattr(mainmod, "AgentLoop", SlowLoop)
    monkeypatch.setattr(mainmod, "build_model", lambda config: TestModel(seed=0, call_tools=[]))

    with TestClient(mainmod.app) as client:
        client.app.state.settings.turn_timeout_seconds = 1
        with client.stream(
            "POST",
            "/agent/turn",
            json=_turn_payload(tmp_path, session_id="sess-timeout"),
            headers=INTERNAL_HEADERS,
        ) as resp:
            events = _sse_events(resp)

    error_events = [data for event, data in events if event == "error"]
    assert error_events
    assert error_events[-1]["code"] == "turn_timeout"


async def test_confirmation_timeout_emits_error_before_deny(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.agent.confirmation.CONFIRMATION_TIMEOUT_SECONDS",
        0.05,
    )
    client = FakeProjectClient()
    agent = build_agent(TestModel(call_tools=["generate_document"]))
    loop = AgentLoop(
        agent=agent,
        project_client=client,
        sandbox_runner=SandboxRunner(timeout_seconds=10),
        max_iterations=6,
    )
    request = AgentTurnRequest(
        project_id="p",
        session_id="sess-ctimeout",
        turn_id="turn-ctimeout",
        message="écrire",
        documents=[],
    )

    events = [event async for event in loop.run_turn(request, turn_id="turn-ctimeout")]
    error_events = [event for event in events if isinstance(event, ErrorEvent)]
    assert any(event.code == "confirmation_timeout" for event in error_events)


async def test_concurrent_gates_with_distinct_turn_ids() -> None:
    gate_a = ConfirmationGate(session_id="sess-multi", turn_id="turn-a")
    gate_b = ConfirmationGate(session_id="sess-multi", turn_id="turn-b")
    await confirmation_registry.register(gate_a)
    await confirmation_registry.register(gate_b)
    try:
        assert confirmation_registry.get_gate("sess-multi", "turn-a") is gate_a
        assert confirmation_registry.get_gate("sess-multi", "turn-b") is gate_b
    finally:
        await confirmation_registry.unregister("sess-multi", "turn-a")
        await confirmation_registry.unregister("sess-multi", "turn-b")


async def test_disconnect_cancels_turn_and_unregisters_gate(
    fake_project_client: FakeProjectClient,
) -> None:
    agent = build_agent(TestModel(seed=0, call_tools=[]))
    loop = AgentLoop(
        agent=agent,
        project_client=fake_project_client,
        sandbox_runner=SandboxRunner(timeout_seconds=10),
        max_iterations=6,
    )
    request = AgentTurnRequest(
        project_id="p",
        session_id="sess-disconnect-loop",
        message="test",
        documents=[],
    )
    cancel_event = asyncio.Event()

    async def cancel_soon() -> None:
        await asyncio.sleep(0.1)
        cancel_event.set()

    cancel_task = asyncio.create_task(cancel_soon())
    events = [
        event
        async for event in loop.run_turn(
            request,
            turn_id="turn-disconnect",
            cancel_event=cancel_event,
        )
    ]
    await cancel_task

    assert confirmation_registry.get_gate("sess-disconnect-loop", "turn-disconnect") is None
    assert events == [] or not any(isinstance(event, ErrorEvent) for event in events)
