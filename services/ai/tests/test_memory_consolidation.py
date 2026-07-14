"""Tests de consolidation mémoire (promotion session → project)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agent.memory_consolidation import (
    apply_fact_to_store,
    consolidate_facts,
    find_matching_memory,
    log_promotion_event,
    parse_contradiction_action,
    parse_facts_from_llm_output,
    promote_session_summary,
    trim_project_memory_store,
)
from app.audit import audit_file_path, read_audit
from app.rag.store import open_memory_store


@pytest.fixture
def memory_store(tmp_path: Path):
    ws = tmp_path / "space"
    ws.mkdir()
    store = open_memory_store(ws / "memory.db")
    yield store
    store.close()


@pytest.fixture
def workspace_dir(tmp_path: Path) -> Path:
    ws = tmp_path / "app_data" / "workspaces" / "ws1" / ".workproba"
    ws.mkdir(parents=True)
    return ws


def test_find_matching_memory_noop_on_exact_duplicate() -> None:
    existing = [{"id": "mem_1", "content": "Le budget RH est de 120k€"}]
    operation, match, score = find_matching_memory(
        existing,
        "Le budget RH est de 120k€",
        update_threshold=0.55,
    )
    assert operation == "NOOP"
    assert match is not None
    assert score == 1.0


def test_find_matching_memory_update_on_overlap(memory_store) -> None:
    memory_store.add_memory(
        content="Le budget RH est de 120k€ pour 2026",
        source="manual",
    )
    operation, match, score = find_matching_memory(
        memory_store.list_memories(),
        "Le budget RH est fixé à 120k€ pour 2026",
        update_threshold=0.55,
    )
    assert operation == "UPDATE"
    assert match is not None
    assert score >= 0.55


@pytest.mark.asyncio
async def test_consolidate_facts_add_update_noop(memory_store) -> None:
    memory_store.add_memory(content="Le client s'appelle Dupont", source="manual")
    result = await consolidate_facts(
        memory_store,
        [
            "Le client s'appelle Dupont",
            "Le budget RH est de 120k€",
            "Le budget RH est fixé à 120k€",
        ],
        session_id="sess-abc",
        max_facts=5,
        update_threshold=0.55,
        contradiction_enabled=False,
        locale="fr",
        settings=object(),
    )
    assert result["counts"]["NOOP"] == 1
    assert result["counts"]["ADD"] >= 1
    memories = memory_store.list_memories()
    assert len(memories) >= 2
    promoted = [item for item in memories if item.get("source") == "session_promotion"]
    assert promoted
    assert any("session:sess-abc" in (item.get("tags") or []) for item in promoted)


@pytest.mark.asyncio
async def test_apply_fact_falls_back_to_update_on_llm_error(
    memory_store, monkeypatch
) -> None:
    memory_store.add_memory(content="Le budget RH est de 120k€", source="manual")

    async def _boom(new_fact, existing_fact, **kwargs):  # noqa: ANN001, ANN003
        raise RuntimeError("llm down")

    monkeypatch.setattr(
        "app.agent.memory_consolidation.resolve_ambiguous_update",
        _boom,
    )

    outcome = await apply_fact_to_store(
        memory_store,
        "Le budget RH est de 150k€",
        "sess-x",
        update_threshold=0.55,
        contradiction_enabled=True,
        locale="fr",
        settings=object(),
    )
    assert outcome["operation"] == "UPDATE"
    assert memory_store.list_memories()[0]["content"] == "Le budget RH est de 150k€"


def test_rank_sessions_by_query_single_token() -> None:
    from app.agent.memory_ranking import rank_sessions_by_query

    sessions = [
        {"id": "1", "title": "Budget RH", "summary": "Discussion budget"},
        {"id": "2", "title": "Chat", "summary": "Le chat dort"},
    ]
    ranked = rank_sessions_by_query(
        sessions,
        "budget",
        k=2,
        min_overlap=2,
    )
    assert len(ranked) == 1
    assert ranked[0]["id"] == "1"


@pytest.mark.asyncio
async def test_apply_fact_delete_on_contradiction(memory_store, monkeypatch) -> None:
    memory_store.add_memory(content="Le budget RH est de 120k€", source="manual")

    async def _delete(new_fact, existing_fact, **kwargs):  # noqa: ANN001, ANN003
        return "DELETE"

    monkeypatch.setattr(
        "app.agent.memory_consolidation.resolve_ambiguous_update",
        _delete,
    )

    outcome = await apply_fact_to_store(
        memory_store,
        "Le budget RH est de 150k€",
        "sess-x",
        update_threshold=0.55,
        contradiction_enabled=True,
        locale="fr",
        settings=object(),
    )
    assert outcome["operation"] == "DELETE"
    memories = memory_store.list_memories()
    assert len(memories) == 1
    assert memories[0]["content"] == "Le budget RH est de 150k€"


def test_parse_contradiction_action_json() -> None:
    assert parse_contradiction_action('{"action":"DELETE"}') == "DELETE"
    assert parse_contradiction_action('{"action":"NOOP"}') == "NOOP"
    assert parse_contradiction_action("Use UPDATE not DELETE") == "UPDATE"


def test_parse_contradiction_action_ignores_prose() -> None:
    assert parse_contradiction_action("Do not DELETE, prefer UPDATE") == "UPDATE"


def test_trim_project_memory_store(memory_store) -> None:
    for index in range(5):
        memory_store.add_memory(content=f"Fait {index}", source="manual")
    removed = trim_project_memory_store(memory_store, 3)
    assert removed == 2
    assert len(memory_store.list_memories()) == 3


def test_parse_facts_from_llm_output_json() -> None:
    facts = parse_facts_from_llm_output(
        '["Budget RH : 120k€", "Client : Dupont"]',
        max_facts=5,
    )
    assert facts == ["Budget RH : 120k€", "Client : Dupont"]


def test_log_promotion_event_writes_audit(workspace_dir: Path) -> None:
    log_promotion_event(
        workspace_dir,
        session_id="sess-1",
        counts={"ADD": 2, "UPDATE": 0, "NOOP": 1, "DELETE": 0},
        facts=["a", "b"],
        pruned=1,
    )
    app_data = workspace_dir.parent.parent.parent
    entries, total = read_audit(app_data, event="memory.promotion")
    assert total == 1
    assert entries[0]["details"]["session_id"] == "sess-1"
    assert entries[0]["details"]["pruned"] == 1
    assert audit_file_path(app_data).is_file()


@pytest.mark.asyncio
async def test_promote_session_summary_with_mocked_extraction(
    memory_store,
    workspace_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_extract(summary, **kwargs):  # noqa: ANN001, ANN003
        return ["Le livrable final est un rapport Word."]

    monkeypatch.setattr(
        "app.agent.memory_consolidation.extract_facts_from_summary",
        _fake_extract,
    )
    result = await promote_session_summary(
        memory_store,
        summary="Décisions : livrable Word.",
        session_id="sess-1",
        workspace_data_dir=workspace_dir,
        settings=object(),
        max_entries=200,
    )
    assert result["facts"] == ["Le livrable final est un rapport Word."]
    assert result["counts"]["ADD"] == 1
    assert memory_store.list_memories()[0]["source"] == "session_promotion"
