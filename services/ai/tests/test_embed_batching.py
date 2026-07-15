"""Tests du découpage des requêtes d'embedding."""

from __future__ import annotations

import pytest

from app.embed_batching import iter_embedding_batches


def test_iter_embedding_batches_splits_by_item_count() -> None:
    batches = list(
        iter_embedding_batches(["a", "b", "c", "d", "e"], max_items=2, max_chars=10_000)
    )
    assert batches == [["a", "b"], ["c", "d"], ["e"]]


def test_iter_embedding_batches_splits_by_char_budget() -> None:
    texts = ["x" * 1200, "y" * 1200, "z" * 1200]
    batches = list(iter_embedding_batches(texts, max_items=100, max_chars=2500))
    assert batches == [["x" * 1200, "y" * 1200], ["z" * 1200]]


def test_iter_embedding_batches_oversized_single_text() -> None:
    big = "a" * 5000
    batches = list(iter_embedding_batches([big, "b"], max_items=10, max_chars=1000))
    assert batches == [[big], ["b"]]


def test_iter_embedding_batches_rejects_invalid_limits() -> None:
    with pytest.raises(ValueError):
        list(iter_embedding_batches(["a"], max_items=0, max_chars=100))
    with pytest.raises(ValueError):
        list(iter_embedding_batches(["a"], max_items=1, max_chars=0))
