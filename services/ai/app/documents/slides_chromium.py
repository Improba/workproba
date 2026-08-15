"""Rendu HTML → PDF/PNG via Chromium (Playwright), optionnel."""

from __future__ import annotations

from app.runtime_chromium import chromium_available, chromium_launch_kwargs

_DEFAULT_TIMEOUT_MS = 30_000
_VIEWPORT = {"width": 1280, "height": 720}


def html_to_pdf_bytes(html: str, *, timeout_ms: int = _DEFAULT_TIMEOUT_MS) -> bytes:
    """Convertit un document HTML en PDF via Chromium.

    HTML local (pas de réseau) : ``load`` plutôt que ``networkidle``.
    Le format de page vient du CSS ``@page``.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        try:
            page = browser.new_page(viewport=_VIEWPORT)
            page.set_content(html, wait_until="load", timeout=timeout_ms)
            page.emulate_media(media="print")
            return page.pdf(print_background=True, prefer_css_page_size=True)
        finally:
            browser.close()


def html_slides_to_pngs(html: str, *, timeout_ms: int = _DEFAULT_TIMEOUT_MS) -> list[bytes]:
    """Capture chaque .wp-slide en PNG (plein cadre 16:9)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        try:
            page = browser.new_page(viewport=_VIEWPORT)
            page.set_content(html, wait_until="load", timeout=timeout_ms)
            locator = page.locator(".wp-slide")
            count = locator.count()
            return [
                locator.nth(i).screenshot(timeout=timeout_ms, type="png")
                for i in range(count)
            ]
        finally:
            browser.close()


__all__ = ["chromium_available", "html_to_pdf_bytes", "html_slides_to_pngs"]
