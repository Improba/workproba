"""Tests rendu HTML slides."""

from __future__ import annotations

from app.documents.slides_html import render_deck_html


def test_render_deck_html_uses_div_wp_slide() -> None:
    html = render_deck_html(
        [{"grammar": "hero", "hierarchy": {"primary": "Titre", "secondary": []}}]
    )
    assert "<div class='wp-slide" in html or '<div class="wp-slide' in html
    assert "<section" not in html
    assert "wp-slide--hero" in html
    assert "Titre" in html


def test_render_deck_html_escapes_script() -> None:
    html = render_deck_html(
        [
            {
                "grammar": "sequence",
                "hierarchy": {
                    "primary": "<script>alert(1)</script>",
                    "secondary": ["<img onerror=alert(1)>"],
                },
            }
        ]
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "onerror" in html  # texte échappé, pas attribut actif


def test_render_deck_html_hero_includes_tertiary() -> None:
    html = render_deck_html(
        [
            {
                "grammar": "hero",
                "hierarchy": {
                    "primary": "Titre",
                    "secondary": ["Lede"],
                    "tertiary": ["Extra"],
                },
            }
        ]
    )
    assert "Lede" in html
    assert "Extra" in html


def test_render_deck_html_split_includes_tertiary() -> None:
    html = render_deck_html(
        [
            {
                "grammar": "split",
                "hierarchy": {
                    "primary": "Comparaison",
                    "secondary": ["Gauche"],
                    "tertiary": ["Droite"],
                },
            }
        ]
    )
    assert "Gauche" in html
    assert "Droite" in html


def test_render_deck_html_includes_tertiary_bullets() -> None:
    html = render_deck_html(
        [
            {
                "grammar": "sequence",
                "hierarchy": {
                    "primary": "Titre",
                    "secondary": ["Puce A"],
                    "tertiary": ["Puce B"],
                },
            }
        ]
    )
    assert "Puce A" in html
    assert "Puce B" in html
