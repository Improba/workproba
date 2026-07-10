"""Tests unitaires RAG (sans réseau)."""

from __future__ import annotations

from pathlib import Path

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
    import asyncio

    results = asyncio.run(store.search(query="x", limit=5))
    assert results == []
    store.close()
