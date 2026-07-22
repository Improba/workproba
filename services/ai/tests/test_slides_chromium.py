"""Tests Chromium optionnel (skip si playwright absent)."""

from __future__ import annotations

import pytest

from app.documents.slides_chromium import chromium_available


def test_chromium_available_is_bool() -> None:
    assert isinstance(chromium_available(), bool)


@pytest.mark.skipif(not chromium_available(), reason="playwright not installed")
def test_html_slides_to_pngs_when_chromium_available() -> None:
    from app.documents.slides_chromium import html_slides_to_pngs
    from app.documents.slides_html import render_deck_html

    html = render_deck_html(
        [{"grammar": "hero", "hierarchy": {"primary": "PNG test", "secondary": []}}]
    )
    pngs = html_slides_to_pngs(html)
    assert len(pngs) == 1
    assert pngs[0][:8] == b"\x89PNG\r\n\x1a\n"
