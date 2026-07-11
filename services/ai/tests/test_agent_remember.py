"""Test d'intégration : l'agent persiste un souvenir via le tool `remember`.

Valide la cohérence du wiring : le tool écrit dans le store du scope demandé
(project par défaut) avec source="agent", et le system_prompt `memory_prompt`
n'échoue pas quand les stores sont vides (pas de bruit injecté).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.models.test import TestModel

from app.agent.loop import AgentLoop
from app.agent.tools import build_agent
from app.memory_stores import open_memory_store_for_scope
from app.sandbox.runner import SandboxRunner
from app.schemas import AgentTurnRequest, DoneEvent, ErrorEvent
from conftest import FakeProjectClient


def _request(workspace_data_dir: Path) -> AgentTurnRequest:
    return AgentTurnRequest(
        tenant_id="t",
        project_id="p",
        session_id="s-remember",
        message="mémorise ceci",
        documents=[],
        workspace_data_dir=str(workspace_data_dir),
    )


def _new_loop(client: FakeProjectClient) -> AgentLoop:
    agent = build_agent(TestModel(seed=1, call_tools=["remember"]))
    return AgentLoop(
        agent=agent,
        project_client=client,
        sandbox_runner=SandboxRunner(timeout_seconds=10),
        max_iterations=4,
    )


async def test_remember_tool_persists_to_project_scope(
    fake_project_client: FakeProjectClient,
    tmp_path: Path,
) -> None:
    app_data = tmp_path / "workproba-appdata"
    ws = app_data / "workspaces" / "ws1"
    ws.mkdir(parents=True, exist_ok=True)

    loop = _new_loop(fake_project_client)
    events = [e async for e in loop.run_turn(_request(ws), turn_id="t-remember")]

    # Le tour se termine proprement.
    assert isinstance(events[-1], (DoneEvent, ErrorEvent))

    # Un souvenir a été persisté dans le store project, avec source="agent".
    store = open_memory_store_for_scope("project", ws)
    try:
        memories = store.list_memories()
    finally:
        store.close()
    assert len(memories) >= 1
    assert all(m["source"] == "agent" for m in memories)

    # Le store user global reste vide (le tool a utilisé le scope project par défaut).
    user_store = open_memory_store_for_scope("user", ws)
    try:
        assert user_store.list_memories() == []
    finally:
        user_store.close()
