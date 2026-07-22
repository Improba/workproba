"""Tests schéma sémantique slides."""

from __future__ import annotations

import pytest

from app.documents.slides_schema import GRAMMARS, normalize_deck, normalize_slide


def test_normalize_legacy_layout_title() -> None:
    slide = normalize_slide({"layout": "title", "title": "Hello", "subtitle": "World"})
    assert slide["grammar"] == "hero"
    assert slide["hierarchy"]["primary"] == "Hello"
    assert slide["hierarchy"]["secondary"] == ["World"]


def test_normalize_grammar_hero() -> None:
    slide = normalize_slide(
        {
            "grammar": "hero",
            "hierarchy": {"primary": "Pitch", "secondary": ["Tagline"]},
        }
    )
    assert slide["grammar"] == "hero"
    assert slide["hierarchy"]["primary"] == "Pitch"


def test_normalize_deck_empty_defaults() -> None:
    deck = normalize_deck(None)
    assert len(deck) == 1
    assert deck[0]["grammar"] == "hero"
    assert deck[0]["hierarchy"]["primary"] == "Présentation"


def test_normalize_rejects_unknown_layout() -> None:
    with pytest.raises(ValueError, match="layout"):
        normalize_slide({"layout": "carousel", "title": "X"})


def test_normalize_rejects_unknown_grammar() -> None:
    with pytest.raises(ValueError, match="grammar"):
        normalize_slide({"grammar": "carousel", "hierarchy": {"primary": "X"}})


def test_all_grammars_are_valid() -> None:
    for grammar in GRAMMARS:
        slide = normalize_slide(
            {
                "grammar": grammar,
                "hierarchy": {"primary": "T", "secondary": ["a", "b"]},
                "visual": {
                    "type": "kpi_row" if grammar == "dashboard" else "none",
                    "items": [{"label": "K", "value": "1"}] if grammar == "dashboard" else [],
                },
            }
        )
        assert slide["grammar"] == grammar
