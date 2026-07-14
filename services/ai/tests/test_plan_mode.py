"""Tests plan mode (propose_plan + /agent/plan/approve)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.models.test import TestModel

import app.auth as authmod
import app.main as mainmod
from app.agent.loop import AgentLoop
from app.agent.plan import PlanGate
from app.agent.tools import build_agent
from app.local_client import LocalProjectClient
from app.schemas import (
    AgentTurnRequest,
    PlanProposedEvent,
    ToolCallResultEvent,
    WorkContributionEvent,
)
from app.sandbox.runner import SandboxRunner


@pytest.fixture(autouse=True)
def _patch_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)


async def _run_loop(
    loop: AgentLoop,
    request: AgentTurnRequest,
    *,
    turn_id: str,
) -> list[Any]:
    events = []
    async for event in loop.run_turn(request, turn_id=turn_id):
        events.append(event)
    return events


def _make_plan_loop(client: LocalProjectClient, project_root: Path) -> AgentLoop:
    agent = build_agent(TestModel(call_tools=["propose_plan"]))
    return AgentLoop(
        agent=agent,
        project_client=client,
        sandbox_runner=SandboxRunner(timeout_seconds=30),
        max_iterations=5,
        project_root=project_root,
    )


@pytest.mark.asyncio
async def test_propose_plan_emits_event_and_waits_approval(tmp_path: Path) -> None:
    client = LocalProjectClient(project_root=tmp_path)
    loop = _make_plan_loop(client, project_root=tmp_path)
    turn_id = "turn-plan-approve"
    request = AgentTurnRequest(
        tenant_id="t",
        project_id=str(tmp_path),
        session_id="sess-plan",
        turn_id=turn_id,
        message="prépare le contrat",
        documents=[],
    )

    async def approve() -> None:
        await asyncio.sleep(0.15)
        gate = mainmod.plan_registry.get_gate("sess-plan", turn_id)
        assert gate is not None
        plan_id = next(iter(gate._pending))
        gate.resolve(plan_id, approved=True)

    approve_task = asyncio.create_task(approve())
    events = await _run_loop(loop, request, turn_id=turn_id)
    await approve_task

    plan_events = [e for e in events if isinstance(e, PlanProposedEvent)]
    assert len(plan_events) == 1
    assert plan_events[0].plan_id
    assert len(plan_events[0].steps) >= 0

    results = [
        e
        for e in events
        if isinstance(e, ToolCallResultEvent) and e.tool_name == "propose_plan"
    ]
    assert len(results) == 1
    assert results[0].is_error is False
    assert results[0].result.get("approved") is True


@pytest.mark.asyncio
async def test_propose_plan_deny_marks_error(tmp_path: Path) -> None:
    client = LocalProjectClient(project_root=tmp_path)
    loop = _make_plan_loop(client, project_root=tmp_path)
    turn_id = "turn-plan-deny"
    request = AgentTurnRequest(
        tenant_id="t",
        project_id=str(tmp_path),
        session_id="sess-plan-deny",
        turn_id=turn_id,
        message="plan complexe",
        documents=[],
    )

    async def deny() -> None:
        await asyncio.sleep(0.15)
        gate = mainmod.plan_registry.get_gate("sess-plan-deny", turn_id)
        assert gate is not None
        plan_id = next(iter(gate._pending))
        gate.resolve(plan_id, approved=False)

    deny_task = asyncio.create_task(deny())
    events = await _run_loop(loop, request, turn_id=turn_id)
    await deny_task

    results = [
        e
        for e in events
        if isinstance(e, ToolCallResultEvent) and e.tool_name == "propose_plan"
    ]
    assert len(results) == 1
    assert results[0].is_error is True
    assert results[0].result.get("cancelled") is True

    contributions = [
        e
        for e in events
        if isinstance(e, WorkContributionEvent)
        and e.contribution_id == results[0].tool_call_id
    ]
    final = [e for e in contributions if e.status != "started"]
    assert len(final) == 1
    assert final[0].status == "cancelled"


def test_plan_approve_http_endpoint() -> None:
    from fastapi.testclient import TestClient

    async def exercise() -> None:
        gate = PlanGate(session_id="sess-http", turn_id="turn-http")
        await mainmod.plan_registry.register(gate)

        async def wait_plan() -> dict[str, Any]:
            return await gate.request_plan(
                steps=[
                    {
                        "tool": "write_docx",
                        "summary": "Créer contrat",
                        "target": "c.docx",
                    }
                ],
                rationale="Tâche multi-étapes",
                locale="fr",
            )

        waiter = asyncio.create_task(wait_plan())
        await asyncio.sleep(0.05)
        plan_id = next(iter(gate._pending))

        with TestClient(mainmod.app) as client:
            resp = client.post(
                "/agent/plan/approve",
                json={
                    "session_id": "sess-http",
                    "turn_id": "turn-http",
                    "plan_id": plan_id,
                    "approved": True,
                },
                headers={"X-Internal-Secret": "desktop-dev-secret"},
            )
            assert resp.status_code == 200

        result = await waiter
        assert result.get("approved") is True
        await mainmod.plan_registry.unregister("sess-http", "turn-http")

    asyncio.run(exercise())
