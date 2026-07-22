"""Rendu HTML → PDF/PNG via Chromium (Playwright), optionnel."""

from __future__ import annotations

_DEFAULT_TIMEOUT_MS = 30_000
_VIEWPORT = {"width": 1280, "height": 720}


def chromium_available() -> bool:
    """True si playwright est importable (chromium peut être absent en CI)."""
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


def html_to_pdf_bytes(html: str, *, timeout_ms: int = _DEFAULT_TIMEOUT_MS) -> bytes:
    """Convertit un document HTML en PDF via Chromium."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport=_VIEWPORT)
            page.set_content(html, wait_until="networkidle", timeout=timeout_ms)
            return page.pdf(
                width="13.333in",
                height="7.5in",
                print_background=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            )
        finally:
            browser.close()


def html_slides_to_pngs(html: str, *, timeout_ms: int = _DEFAULT_TIMEOUT_MS) -> list[bytes]:
    """Capture chaque .wp-slide en PNG (plein cadre 16:9)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport=_VIEWPORT)
            page.set_content(html, wait_until="networkidle", timeout=timeout_ms)
            locator = page.locator(".wp-slide")
            count = locator.count()
            return [
                locator.nth(i).screenshot(timeout=timeout_ms, type="png")
                for i in range(count)
            ]
        finally:
            browser.close()


__all__ = ["chromium_available", "html_to_pdf_bytes", "html_slides_to_pngs"]
