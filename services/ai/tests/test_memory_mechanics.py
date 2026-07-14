"""Tests mécaniques transverses (ranking, dédup, promotion)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.models.test import TestModel

from app.agent.memory_consolidation import (
    apply_explicit_memory_heuristic,
    session_has_promoted_facts,
)
from app.agent.memory_ranking import rank_memories_by_query
from app.agent.tools import ToolContext, ToolDeps, build_agent
from app.memory_stores import open_memory_store_for_scope
from app.rag.store import open_memory_store
from app.sandbox.runner import SandboxRunner
from conftest import FakeProjectClient


@pytest.fixture
def memory_store(tmp_path: Path):
    ws = tmp_path / "space"
    ws.mkdir()
    store = open_memory_store(ws / "memory.db")
    yield store
    store.close()


def test_rank_memories_skips_zero_overlap_when_query_specific() -> None:
    items = [
        {"id": "1", "content": "Le chat dort sur le canapé"},
        {"id": "2", "content": "La réunion projet est demain"},
    ]
    ranked = rank_memories_by_query(items, "budget annuel", k=2)
    assert ranked == []


def test_apply_explicit_memory_heuristic_updates_similar(memory_store) -> None:
    memory_store.add_memory(content="Le budget RH est de 120k€", source="manual")
    memory, operation = apply_explicit_memory_heuristic(
        memory_store,
        "Le budget RH est fixé à 120k€",
        source="agent",
    )
    assert operation == "UPDATE"
    assert memory["content"] == "Le budget RH est fixé à 120k€"
    assert len(memory_store.list_memories()) == 1


def test_session_has_promoted_facts_detects_tag(memory_store) -> None:
    memory_store.add_memory(
        content="Livrable Word",
        source="session_promotion",
        tags=["session:sess-1", "promoted"],
    )
    assert session_has_promoted_facts(memory_store, "sess-1") is True
    assert session_has_promoted_facts(memory_store, "sess-2") is False


def _relevant_sessions_prompt_fn(agent):
    for runner in agent._system_prompt_functions:
        if runner.function.__name__ == "relevant_sessions_prompt":
            return runner.function
    raise AssertionError("relevant_sessions_prompt not registered")


class _FakeRunContext:
    def __init__(self, deps: ToolDeps) -> None:
        self.deps = deps


def test_relevant_sessions_skips_already_promoted(tmp_path: Path) -> None:
    ws = tmp_path / "workspaces" / "ws1"
    conv = ws / "conversations"
    conv.mkdir(parents=True)
    (conv / "other.json").write_text(
        '{"id":"other","title":"Budget RH","summary":"Budget fixé à 120k","updatedAt":"2026-07-10T12:00:00Z"}',
        encoding="utf-8",
    )

    store = open_memory_store_for_scope("project", ws)
    store.add_memory(
        content="Budget fixé à 120k",
        source="session_promotion",
        tags=["session:other", "promoted"],
    )
    store.close()

    agent = build_agent(TestModel(), locale="fr")
    prompt_fn = _relevant_sessions_prompt_fn(agent)
    ctx = _FakeRunContext(
        ToolDeps(
            context=ToolContext(
                tenant_id="t",
                project_id="p",
                session_id="current",
                documents=[],
                workspace_data_dir=ws,
                locale="fr",
                last_user_query="budget RH",
            ),
            project_client=FakeProjectClient(),
            sandbox_runner=SandboxRunner(timeout_seconds=10),
        )
    )

    assert prompt_fn(ctx) == ""


def test_relevant_sessions_injects_unpromoted_summary(tmp_path: Path) -> None:
    ws = tmp_path / "workspaces" / "ws1"
    conv = ws / "conversations"
    conv.mkdir(parents=True)
    (conv / "other.json").write_text(
        '{"id":"other","title":"Budget RH","summary":"Le budget annuel RH est de 120k€","updatedAt":"2026-07-10T12:00:00Z"}',
        encoding="utf-8",
    )

    agent = build_agent(TestModel(), locale="fr")
    prompt_fn = _relevant_sessions_prompt_fn(agent)
    ctx = _FakeRunContext(
        ToolDeps(
            context=ToolContext(
                tenant_id="t",
                project_id="p",
                session_id="current",
                documents=[],
                workspace_data_dir=ws,
                locale="fr",
                last_user_query="budget RH annuel",
            ),
            project_client=FakeProjectClient(),
            sandbox_runner=SandboxRunner(timeout_seconds=10),
        )
    )

    text = prompt_fn(ctx)
    assert "120k" in text
    assert "<untrusted>" in text
