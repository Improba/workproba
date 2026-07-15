"""Tests unitaires RAG (sans réseau)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from app.rag.store import RagStore, chunk_text


def test_chunk_text_basic() -> None:
    chunks = chunk_text("abcdefghij", chunk_size=4, overlap=1)
    # chunks: [0:4]="abcd", [3:7]="defg", [6:10]="ghij"
    assert chunks == ["abcd", "defg", "ghij"]


def test_chunk_text_short() -> None:
    assert chunk_text("abc", chunk_size=1200, overlap=120) == ["abc"]


def test_chunk_text_empty() -> None:
    assert chunk_text("", chunk_size=1200, overlap=120) == []


def test_chunk_text_invalid_overlap() -> None:
    with pytest.raises(ValueError):
        chunk_text("abc", chunk_size=4, overlap=4)


def test_chunk_text_invalid_chunk_size() -> None:
    with pytest.raises(ValueError):
        chunk_text("abc", chunk_size=0, overlap=0)


def test_rag_store_disabled_when_no_embedding_model(tmp_path: Path) -> None:
    # La construction ne connecte pas la DB (lazy) ; on valide juste l'init.
    store = RagStore(
        db_path=tmp_path / "memory.db",
        embedding_model="mistral/mistral-embed",
        embedding_base_url="https://api.mistral.ai/v1",
        embedding_api_key="key",
    )
    # search avant indexage -> dim inconnue -> liste vide (pas d'appel embedding).
    results = asyncio.run(store.search(query="x", limit=5))
    assert results == []
    store.close()


def test_embed_batches_api_calls(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    batch_sizes: list[int] = []

    async def fake_aembedding(**kwargs: Any) -> Any:
        batch = kwargs["input"]
        batch_sizes.append(len(batch))
        dim = 4
        return type(
            "EmbeddingResponse",
            (),
            {"data": [{"embedding": [0.0] * dim} for _ in batch]},
        )()

    monkeypatch.setattr("app.rag.store.litellm.aembedding", fake_aembedding)

    store = RagStore(
        db_path=tmp_path / "memory.db",
        embedding_model="mistral/mistral-embed",
        embedding_batch_size=10,
        embedding_batch_max_chars=100_000,
    )
    vectors = asyncio.run(store._embed(["chunk"] * 25))
    assert len(vectors) == 25
    assert batch_sizes == [10, 10, 5]
    store.close()


def test_embed_batches_respects_char_budget(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    batch_sizes: list[int] = []

    async def fake_aembedding(**kwargs: Any) -> Any:
        batch = kwargs["input"]
        batch_sizes.append(len(batch))
        dim = 4
        return type(
            "EmbeddingResponse",
            (),
            {"data": [{"embedding": [0.0] * dim} for _ in batch]},
        )()

    monkeypatch.setattr("app.rag.store.litellm.aembedding", fake_aembedding)

    store = RagStore(
        db_path=tmp_path / "memory.db",
        embedding_model="mistral/mistral-embed",
        embedding_batch_size=100,
        embedding_batch_max_chars=2500,
    )
    vectors = asyncio.run(store._embed(["x" * 1200] * 5))
    assert len(vectors) == 5
    assert batch_sizes == [2, 2, 1]
    store.close()
