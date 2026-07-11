"""Tests confirmation avant écriture (T-D3b) et gating sandbox (T-SB2/T-SB3)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.models.test import TestModel

import app.auth as authmod
import app.main as mainmod
from app.agent.confirmation import ConfirmationGate, confirmation_registry
from app.agent.loop import AgentLoop
from app.agent.tools import build_agent
from app.capabilities import Capabilities, detect_capabilities
from app.local_client import LocalProjectClient
from app.sandbox.runner import SandboxRunner
from app.schemas import (
    AgentTurnRequest,
    ConfirmationRequestEvent,
    ToolCallResultEvent,
)

from conftest import FakeProjectClient


def _tool_names(ui_mode: str, *, sandbox_available: bool = True) -> list[str]:
    agent = build_agent(
        TestModel(),
        ui_mode=ui_mode,  # type: ignore[arg-type]
        sandbox_available=sandbox_available,
    )
    return sorted(agent._function_toolset.tools.keys())


def test_run_code_hidden_in_guided_mode() -> None:
    names = _tool_names("guided")
    assert "run_code" not in names
    assert "generate_document" in names


def test_run_code_hidden_in_locked_mode() -> None:
    names = _tool_names("locked")
    assert "run_code" not in names


def test_run_code_exposed_in_advanced_mode() -> None:
    names = _tool_names("advanced")
    assert "run_code" in names


def test_get_capabilities_reflects_docker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mainmod, "detect_capabilities", lambda: Capabilities(docker=True, sandbox_available=True))
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)

    with TestClient(mainmod.app) as client:
        resp = client.get(
            "/capabilities",
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"docker": True, "sandbox_available": True}


def test_get_capabilities_docker_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mainmod,
        "detect_capabilities",
        lambda: Capabilities(docker=False, sandbox_available=False),
    )
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)

    with TestClient(mainmod.app) as client:
        resp = client.get(
            "/capabilities",
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
    assert resp.status_code == 200
    assert resp.json()["docker"] is False
    assert resp.json()["sandbox_available"] is False


def test_startup_without_docker_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.capabilities.detect_docker", lambda: False)
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)

    with TestClient(mainmod.app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200

    caps = detect_capabilities()
    assert caps.docker is False
    assert caps.sandbox_available is False


async def _run_loop(
    loop: AgentLoop,
    request: AgentTurnRequest,
    *,
    turn_id: str = "turn-test",
) -> list[Any]:
    return [event async for event in loop.run_turn(request, turn_id=turn_id)]


def _make_generate_loop(
    client: FakeProjectClient,
    *,
    project_root: Path | None = None,
) -> AgentLoop:
    agent = build_agent(TestModel(call_tools=["generate_document"]))
    return AgentLoop(
        agent=agent,
        project_client=client,
        sandbox_runner=SandboxRunner(timeout_seconds=10),
        max_iterations=6,
        project_root=project_root,
    )


async def test_confirmation_request_emitted_before_write() -> None:
    client = FakeProjectClient()
    loop = _make_generate_loop(client)
    turn_id = "turn-confirm-1"
    request = AgentTurnRequest(
        tenant_id="t",
        project_id="p",
        session_id="sess-confirm-1",
        turn_id=turn_id,
        message="écrire",
        documents=[],
    )

    async def approve_after_delay() -> None:
        await asyncio.sleep(0.15)
        gate = mainmod.confirmation_registry.get_gate("sess-confirm-1", turn_id)
        assert gate is not None
        confirmation_id = next(iter(gate._pending))
        gate.resolve(confirmation_id, "approve")

    approve_task = asyncio.create_task(approve_after_delay())
    events = await _run_loop(loop, request, turn_id=turn_id)
    await approve_task

    confirm_events = [e for e in events if isinstance(e, ConfirmationRequestEvent)]
    assert len(confirm_events) == 1
    confirm = confirm_events[0]
    assert confirm.turn_id == turn_id
    assert confirm.tool_name == "generate_document"
    assert confirm.action == "create"
    assert confirm.confirmation_id.startswith("cf_")
    assert confirm.tool_call_id
    assert confirm.human_summary.startswith("Je vais créer")


async def test_confirmation_approve_writes_and_succeeds(tmp_path: Path) -> None:
    client = LocalProjectClient(project_root=tmp_path)
    loop = _make_generate_loop(client, project_root=tmp_path)
    turn_id = "turn-approve"
    request = AgentTurnRequest(
        tenant_id="t",
        project_id=str(tmp_path),
        session_id="sess-approve",
        turn_id=turn_id,
        message="écrire",
        documents=[],
    )

    async def approve() -> None:
        await asyncio.sleep(0.15)
        gate = mainmod.confirmation_registry.get_gate("sess-approve", turn_id)
        assert gate is not None
        confirmation_id = next(iter(gate._pending))
        gate.resolve(confirmation_id, "approve")

    approve_task = asyncio.create_task(approve())
    events = await _run_loop(loop, request, turn_id=turn_id)
    await approve_task

    target = tmp_path / "a"
    assert target.is_file()

    snapshots_dir = tmp_path / ".workproba" / "versions" / "sess-approve"
    assert not snapshots_dir.exists()

    results = [
        e
        for e in events
        if isinstance(e, ToolCallResultEvent) and e.tool_name == "generate_document"
    ]
    assert len(results) == 1
    assert results[0].is_error is False
    assert results[0].result.get("metadata", {}).get("saved") is True


async def test_confirmation_deny_cancels_without_write(tmp_path: Path) -> None:
    existing = tmp_path / "existant.md"
    existing.write_text("ancien contenu", encoding="utf-8")

    client = LocalProjectClient(project_root=tmp_path)
    loop = _make_generate_loop(client, project_root=tmp_path)
    turn_id = "turn-deny"
    request = AgentTurnRequest(
        tenant_id="t",
        project_id=str(tmp_path),
        session_id="sess-deny",
        turn_id=turn_id,
        message="modifier",
        documents=[],
    )

    async def deny() -> None:
        await asyncio.sleep(0.15)
        gate = mainmod.confirmation_registry.get_gate("sess-deny", turn_id)
        assert gate is not None
        confirmation_id = next(iter(gate._pending))
        gate.resolve(confirmation_id, "deny")

    deny_task = asyncio.create_task(deny())
    events = await _run_loop(loop, request, turn_id=turn_id)
    await deny_task

    assert existing.read_text(encoding="utf-8") == "ancien contenu"
    snapshots_dir = tmp_path / ".workproba" / "versions" / "sess-deny"
    assert not snapshots_dir.exists()

    results = [
        e
        for e in events
        if isinstance(e, ToolCallResultEvent) and e.tool_name == "generate_document"
    ]
    assert len(results) == 1
    result = results[0]
    assert result.is_error is True
    assert result.result == {
        "cancelled": True,
        "message": "Action annulée par l'utilisateur",
    }
    assert result.human_summary == "Action annulée"


async def test_confirmation_modify_action_for_existing_file(tmp_path: Path) -> None:
    (tmp_path / "a").write_text("v1", encoding="utf-8")
    ws_data = tmp_path / "ws_data"
    ws_data.mkdir()
    client = LocalProjectClient(project_root=tmp_path, workspace_data_dir=ws_data)
    loop = _make_generate_loop(client, project_root=tmp_path)
    turn_id = "turn-modify"
    request = AgentTurnRequest(
        tenant_id="t",
        project_id=str(tmp_path),
        workspace_data_dir=str(ws_data),
        session_id="sess-modify",
        turn_id=turn_id,
        message="modifier",
        documents=[],
    )

    async def approve() -> None:
        await asyncio.sleep(0.15)
        gate = mainmod.confirmation_registry.get_gate("sess-modify", turn_id)
        assert gate is not None
        confirmation_id = next(iter(gate._pending))
        gate.resolve(confirmation_id, "approve")

    approve_task = asyncio.create_task(approve())
    events = await _run_loop(loop, request, turn_id=turn_id)
    await approve_task

    confirm = next(e for e in events if isinstance(e, ConfirmationRequestEvent))
    assert confirm.action == "modify"
    assert confirm.proposed_path == "a"

    from app.versions import versions_dir_for_file

    versions_dir = versions_dir_for_file(ws_data, "a")
    assert versions_dir.is_dir()


def test_agent_confirm_unknown_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)

    with TestClient(mainmod.app) as client:
        resp = client.post(
            "/agent/confirm",
            json={
                "session_id": "missing-session",
                "confirmation_id": "cf_missing",
                "decision": "approve",
            },
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
    assert resp.status_code == 404


async def test_agent_confirm_resolves_pending_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)

    turn_id = "turn-resolve"
    gate = ConfirmationGate(session_id="sess-resolve", turn_id=turn_id)
    await confirmation_registry.register(gate)

    wait_event = asyncio.Event()
    confirmation_id = "cf_test_confirm"
    from app.agent import confirmation as confirmation_mod

    pending = confirmation_mod._PendingConfirmation(
        session_id="sess-resolve",
        turn_id=turn_id,
        tool_call_id="tc_1",
    )
    pending.event = wait_event
    gate._pending[confirmation_id] = pending

    try:
        with TestClient(mainmod.app) as client:
            resp = client.post(
                "/agent/confirm",
                json={
                    "session_id": "sess-resolve",
                    "turn_id": turn_id,
                    "confirmation_id": confirmation_id,
                    "decision": "approve",
                },
                headers={"X-Internal-Secret": "desktop-dev-secret"},
            )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        assert wait_event.is_set()
        assert pending.decision == "approve"
    finally:
        await confirmation_registry.unregister("sess-resolve", turn_id)


async def test_run_code_unavailable_in_advanced_without_docker() -> None:
    agent = build_agent(
        TestModel(call_tools=["run_code"]),
        ui_mode="advanced",
        sandbox_available=False,
    )
    loop = AgentLoop(
        agent=agent,
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=10),
        max_iterations=6,
    )
    request = AgentTurnRequest(
        tenant_id="t",
        project_id="p",
        session_id="sess-sandbox",
        message="calcul",
        documents=[],
        ui_mode="advanced",
    )
    events = await _run_loop(loop, request)
    results = [
        e for e in events if isinstance(e, ToolCallResultEvent) and e.tool_name == "run_code"
    ]
    assert results
    assert results[0].is_error is True
    assert "Sandbox indisponible" in str(results[0].result)
