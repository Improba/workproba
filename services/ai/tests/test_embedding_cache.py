"""Tests du cache d'embeddings pour le ranking mémoire."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.agent.embedding_cache import (
    EmbeddingCache,
    cache_key,
    content_fingerprint,
    embed_texts_cached,
    reset_embedding_cache,
)
from app.agent.memory_embeddings import prepare_memory_ranking_context


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    reset_embedding_cache()
    yield
    reset_embedding_cache()


def test_content_fingerprint_stable() -> None:
    assert content_fingerprint("  Budget RH  ") == content_fingerprint("Budget RH")
    assert content_fingerprint("A") != content_fingerprint("B")


def test_cache_key_isolates_models() -> None:
    assert cache_key("model-a", "hello") != cache_key("model-b", "hello")


def test_cache_key_isolates_base_urls() -> None:
    assert cache_key(
        "ollama/nomic-embed-text",
        "hello",
        base_url="http://127.0.0.1:11434/v1",
    ) != cache_key(
        "ollama/nomic-embed-text",
        "hello",
        base_url="http://192.168.1.10:11434/v1",
    )


@pytest.mark.asyncio
async def test_embed_texts_cached_dedupes_duplicate_texts_in_batch() -> None:
    calls: list[list[str]] = []

    async def fake_embed(texts: list[str], **kwargs: Any) -> list[list[float]]:
        _ = kwargs
        calls.append(list(texts))
        return [[float(index), 0.3] for index, _text in enumerate(texts)]

    cache = EmbeddingCache(max_entries=16)
    vectors = await embed_texts_cached(
        ["alpha", "alpha", "beta"],
        model="test/embed",
        cache=cache,
        embed_fn=fake_embed,
    )

    assert vectors == [[0.0, 0.3], [0.0, 0.3], [1.0, 0.3]]
    assert calls == [["alpha", "beta"]]


def test_embedding_cache_lru_eviction() -> None:
    cache = EmbeddingCache(max_entries=2)
    cache.put("a", (1.0,))
    cache.put("b", (2.0,))
    cache.put("c", (3.0,))
    assert cache.get("a") is None
    assert cache.get("b") == (2.0,)
    assert cache.get("c") == (3.0,)


@pytest.mark.asyncio
async def test_embed_texts_cached_partial_hits(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    async def fake_embed(texts: list[str], **kwargs: Any) -> list[list[float]]:
        _ = kwargs
        calls.append(list(texts))
        return [[float(index), 0.5] for index, _text in enumerate(texts)]

    cache = EmbeddingCache(max_entries=16)
    first = await embed_texts_cached(
        ["alpha", "beta"],
        model="test/embed",
        cache=cache,
        embed_fn=fake_embed,
    )
    second = await embed_texts_cached(
        ["alpha", "gamma"],
        model="test/embed",
        cache=cache,
        embed_fn=fake_embed,
    )

    assert first == [[0.0, 0.5], [1.0, 0.5]]
    assert second[0] == [0.0, 0.5]
    assert second[1] == [0.0, 0.5]
    assert calls == [["alpha", "beta"], ["gamma"]]
    assert cache.stats().hits == 1
    assert cache.stats().misses == 3


@pytest.mark.asyncio
async def test_long_conversation_reembeds_only_query(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    embed_calls: list[list[str]] = []

    async def counting_embed(texts: list[str], **kwargs: Any) -> list[list[float]]:
        _ = kwargs
        embed_calls.append(list(texts))
        return [[float(index), 0.1] for index, _text in enumerate(texts)]

    monkeypatch.setattr(
        "app.agent.embedding_cache.embed_texts",
        counting_embed,
    )

    workspace = tmp_path / "ws"
    workspace.mkdir()
    memories = [
        {"id": "m1", "content": "Budget RH annuel validé"},
        {"id": "m2", "content": "Client ACME - contrat cadre"},
    ]
    sessions = [
        {"id": "s1", "title": "Réunion budget", "summary": "Décisions RH 2026"},
    ]

    await prepare_memory_ranking_context(
        query="Quel est le budget RH ?",
        workspace_data_dir=workspace,
        sessions=sessions,
        embedding_model="test/embed",
        memories=memories,
    )
    first_batch_size = len(embed_calls[-1])

    await prepare_memory_ranking_context(
        query="Rappelle-moi le client principal",
        workspace_data_dir=workspace,
        sessions=sessions,
        embedding_model="test/embed",
        memories=memories,
    )

    assert first_batch_size == 4
    assert embed_calls[-1] == ["Rappelle-moi le client principal"]


@pytest.mark.asyncio
async def test_new_memory_content_triggers_embedding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    embed_calls: list[list[str]] = []

    async def counting_embed(texts: list[str], **kwargs: Any) -> list[list[float]]:
        _ = kwargs
        embed_calls.append(list(texts))
        return [[float(index), 0.2] for index, _text in enumerate(texts)]

    monkeypatch.setattr(
        "app.agent.embedding_cache.embed_texts",
        counting_embed,
    )

    workspace = tmp_path / "ws"
    workspace.mkdir()
    base_memories = [{"id": "m1", "content": "Budget RH annuel"}]

    await prepare_memory_ranking_context(
        query="budget",
        workspace_data_dir=workspace,
        sessions=[],
        embedding_model="test/embed",
        memories=base_memories,
    )

    extended_memories = [
        *base_memories,
        {"id": "m2", "content": "Nouveau fait promu en mémoire"},
    ]
    await prepare_memory_ranking_context(
        query="budget",
        workspace_data_dir=workspace,
        sessions=[],
        embedding_model="test/embed",
        memories=extended_memories,
    )

    assert "Nouveau fait promu en mémoire" in embed_calls[-1]
    assert "Budget RH annuel" not in embed_calls[-1]
