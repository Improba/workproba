"""Tests ranking mémoire hybride (sémantique + lexical)."""

from __future__ import annotations

import math

from app.agent.memory_ranking import (
    cosine_similarity,
    rank_memories_hybrid,
    rank_sessions_hybrid,
)


def _item(content: str, item_id: str = "1") -> dict:
    return {"id": item_id, "content": content}


def test_cosine_similarity_identical_vectors() -> None:
    vector = [1.0, 0.0, 0.0]
    assert math.isclose(cosine_similarity(vector, vector), 1.0)


def test_cosine_similarity_orthogonal_vectors() -> None:
    assert math.isclose(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0)


def test_rank_memories_hybrid_prefers_semantic_match_without_lexical_overlap() -> None:
    items = [
        _item("La réunion projet est demain", "1"),
        _item("Allocation budgétaire annuelle validée", "2"),
    ]
    query_embedding = (1.0, 0.0)
    item_embeddings = {
        "1": (0.0, 1.0),
        "2": (0.95, 0.05),
    }
    ranked = rank_memories_hybrid(
        items,
        "enveloppe financière annuelle",
        k=1,
        query_embedding=query_embedding,
        item_embeddings=item_embeddings,
        semantic_weight=0.9,
        min_semantic_score=0.2,
    )
    assert ranked[0]["id"] == "2"


def test_rank_memories_hybrid_falls_back_to_lexical_without_embeddings() -> None:
    items = [
        _item("Le chat dort sur le canapé", "1"),
        _item("La réunion projet est demain", "2"),
    ]
    ranked = rank_memories_hybrid(items, "chat canapé", k=1)
    assert ranked[0]["id"] == "1"


def test_rank_sessions_hybrid_prefers_newer_session_on_tie() -> None:
    sessions = [
        {"id": "new", "title": "Budget RH", "summary": "Suivi annuel"},
        {"id": "old", "title": "Budget RH", "summary": "Archive 2024"},
    ]
    ranked = rank_sessions_hybrid(
        sessions,
        "budget RH",
        k=1,
        query_embedding=(1.0, 0.0),
        session_embeddings={
            "new": (0.9, 0.1),
            "old": (0.89, 0.1),
        },
        semantic_weight=0.95,
        min_semantic_score=0.2,
        min_overlap=2,
    )
    assert ranked[0]["id"] == "new"


def test_rank_sessions_hybrid_uses_session_id_embeddings() -> None:
    sessions = [
        {"id": "s1", "title": "Notes diverses", "summary": "Sans lien"},
        {"id": "s2", "title": "Pilotage financier", "summary": "Suivi enveloppe annuelle"},
    ]
    ranked = rank_sessions_hybrid(
        sessions,
        "budget annuel",
        k=1,
        query_embedding=(1.0, 0.0),
        session_embeddings={
            "s1": (0.0, 1.0),
            "s2": (0.9, 0.1),
        },
        semantic_weight=0.85,
        min_semantic_score=0.2,
        min_overlap=2,
    )
    assert ranked[0]["id"] == "s2"


def test_rank_memories_hybrid_ignores_unembedded_items_without_lexical_match() -> None:
    items = [
        _item("La réunion projet est demain", "unembedded"),
        _item("Allocation budgétaire annuelle validée", "semantic"),
    ]

    ranked = rank_memories_hybrid(
        items,
        "enveloppe financière annuelle",
        k=2,
        query_embedding=(1.0, 0.0),
        item_embeddings={
            "semantic": (0.95, 0.05),
        },
        semantic_weight=0.9,
        min_semantic_score=0.2,
    )

    assert [item["id"] for item in ranked] == ["semantic"]


def test_rank_sessions_hybrid_ignores_unembedded_items_without_lexical_match() -> None:
    sessions = [
        {"id": "unembedded", "title": "Notes diverses", "summary": "Sans lien"},
        {"id": "semantic", "title": "Pilotage financier", "summary": "Allocation budgétaire validée"},
    ]

    ranked = rank_sessions_hybrid(
        sessions,
        "enveloppe financière annuelle",
        k=2,
        query_embedding=(1.0, 0.0),
        session_embeddings={
            "semantic": (0.95, 0.05),
        },
        semantic_weight=0.9,
        min_semantic_score=0.2,
        min_overlap=2,
    )

    assert [session["id"] for session in ranked] == ["semantic"]


def test_rank_memories_hybrid_excludes_zero_overlap_when_query_embedding_only() -> None:
    items = [
        _item("La réunion projet est demain", "unembedded"),
        _item("Suivi enveloppe financière interne", "lexical"),
    ]

    ranked = rank_memories_hybrid(
        items,
        "enveloppe financière",
        k=2,
        query_embedding=(1.0, 0.0),
        item_embeddings=None,
        semantic_weight=0.9,
        min_semantic_score=0.2,
    )

    assert [item["id"] for item in ranked] == ["lexical"]
