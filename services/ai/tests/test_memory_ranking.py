from __future__ import annotations

from app.agent.memory_ranking import dedupe_memories_keep_order, rank_memories_by_query


def _item(content: str, item_id: str = "1") -> dict:
    return {"id": item_id, "content": content}


def test_rank_memories_by_query_prefers_overlap() -> None:
    items = [
        _item("Le chat dort sur le canapé", "1"),
        _item("La réunion projet est demain", "2"),
        _item("Le chat aime le canapé", "3"),
    ]
    ranked = rank_memories_by_query(items, "chat canapé", k=2)
    contents = [item["content"] for item in ranked]
    assert "Le chat dort sur le canapé" in contents
    assert "Le chat aime le canapé" in contents
    assert "La réunion projet est demain" not in contents


def test_rank_memories_by_query_tiebreaks_by_recency() -> None:
    items = [
        _item("alpha beta", "1"),
        _item("alpha beta gamma", "2"),
    ]
    ranked = rank_memories_by_query(items, "alpha beta", k=1)
    assert ranked[0]["id"] == "2"


def test_rank_memories_empty_query_returns_recent() -> None:
    items = [
        _item("ancien", "1"),
        _item("moyen", "2"),
        _item("récent", "3"),
    ]
    ranked = rank_memories_by_query(items, "", k=2)
    assert [item["id"] for item in ranked] == ["2", "3"]


def test_dedupe_memories_keep_order() -> None:
    items = [
        _item("  Même   contenu  ", "1"),
        _item("même contenu", "2"),
        _item("autre", "3"),
    ]
    deduped = dedupe_memories_keep_order(items)
    assert len(deduped) == 2
    assert deduped[0]["id"] == "1"
    assert deduped[1]["id"] == "3"
