"""Unit tests for eval metrics (offline, no network)."""

from __future__ import annotations

import pytest

from evals.metrics import precision_at_k, recall_at_k


def test_recall_at_k_full_hit() -> None:
    assert recall_at_k(["a", "b", "c"], ["a", "b"], k=2) == 1.0


def test_recall_at_k_partial_hit() -> None:
    assert recall_at_k(["a", "x"], ["a", "b"], k=2) == 0.5


def test_recall_at_k_no_hit() -> None:
    assert recall_at_k(["x", "y"], ["a", "b"], k=2) == 0.0


def test_recall_at_k_respects_k() -> None:
    assert recall_at_k(["a", "b", "c"], ["c"], k=2) == 0.0
    assert recall_at_k(["a", "b", "c"], ["c"], k=3) == 1.0


def test_recall_at_k_empty_relevant() -> None:
    assert recall_at_k([], [], k=2) == 1.0
    assert recall_at_k(["a"], [], k=2) == 0.0


def test_recall_at_k_invalid_k() -> None:
    with pytest.raises(ValueError):
        recall_at_k(["a"], ["a"], k=0)


def test_precision_at_k() -> None:
    assert precision_at_k(["a", "b", "x"], ["a", "b", "c"], k=3) == pytest.approx(2 / 3)
    assert precision_at_k([], ["a"], k=2) == 0.0


def test_precision_at_k_invalid_k() -> None:
    with pytest.raises(ValueError):
        precision_at_k(["a"], ["a"], k=0)
