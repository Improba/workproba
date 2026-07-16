"""Retrieval metric helpers for eval cases."""

from __future__ import annotations


def recall_at_k(
    retrieved_ids: list[str],
    relevant_ids: list[str],
    k: int,
) -> float:
    """Fraction of relevant document ids found in the top-k retrieved ids."""
    if k < 1:
        raise ValueError("k must be >= 1")
    if not relevant_ids:
        return 1.0 if not retrieved_ids[:k] else 0.0
    top_k = retrieved_ids[:k]
    hits = sum(1 for doc_id in relevant_ids if doc_id in top_k)
    return hits / len(relevant_ids)


def precision_at_k(
    retrieved_ids: list[str],
    relevant_ids: list[str],
    k: int,
) -> float:
    """Fraction of top-k retrieved ids that are relevant."""
    if k < 1:
        raise ValueError("k must be >= 1")
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    relevant = set(relevant_ids)
    hits = sum(1 for doc_id in top_k if doc_id in relevant)
    return hits / len(top_k)
