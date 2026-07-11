"""Moteur browser Playwright (lazy init, session par plugin_data_dir)."""

from __future__ import annotations

import asyncio
import base64
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from app.i18n import t
from app.plugins.workproba_browser import manifest

logger = logging.getLogger(__name__)

ALLOWED_SCHEMES = frozenset({"http", "https"})
FORBIDDEN_SCHEMES = frozenset({"file", "javascript", "data", "vbscript"})

_ENGINE_REGISTRY: dict[str, BrowserEngine] = {}
_ENGINE_FACTORY: type[BrowserEngine] | None = None


class BrowserError(ValueError):
    """Erreur métier browser (code = message d'erreur i18n)."""


def validate_navigation_url(url: str) -> str:
    """Autorise http/https uniquement."""
    cleaned = url.strip()
    if not cleaned:
        raise BrowserError("browser_url_invalid")
    parsed = urlparse(cleaned)
    scheme = (parsed.scheme or "").lower()
    if scheme in FORBIDDEN_SCHEMES or scheme not in ALLOWED_SCHEMES:
        raise BrowserError("browser_url_scheme_forbidden")
    if not parsed.netloc:
        raise BrowserError("browser_url_invalid")
    return cleaned


def _engine_key(plugin_data_dir: Path) -> str:
    return str(plugin_data_dir.expanduser().resolve())


def get_engine(plugin_data_dir: Path) -> BrowserEngine:
    key = _engine_key(plugin_data_dir)
    if key not in _ENGINE_REGISTRY:
        factory = _ENGINE_FACTORY or BrowserEngine
        _ENGINE_REGISTRY[key] = factory(plugin_data_dir)
    return _ENGINE_REGISTRY[key]


def close_engine(plugin_data_dir: Path) -> None:
    key = _engine_key(plugin_data_dir)
    engine = _ENGINE_REGISTRY.pop(key, None)
    if engine is not None:
        engine.close_sync()


def set_engine_factory(factory: type[BrowserEngine] | None) -> None:
    """Point d'injection pour les tests (mock engine)."""
    global _ENGINE_FACTORY
    _ENGINE_FACTORY = factory
    _ENGINE_REGISTRY.clear()


def ensure_playwright_installed(*, locale: str = "fr") -> None:
    """Vérifie playwright ; tente une installation lazy si absent."""
    try:
        import playwright  # noqa: F401
    except ImportError:
        logger.info("playwright missing, attempting lazy install")
        install = subprocess.run(
            [sys.executable, "-m", "pip", "install", "playwright"],
            capture_output=True,
            text=True,
            check=False,
        )
        if install.returncode != 0:
            raise BrowserError("browser_not_available") from None
        try:
            import playwright  # noqa: F401
        except ImportError:
            raise BrowserError("browser_not_available") from None

    browser_install = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True,
        text=True,
        check=False,
    )
    if browser_install.returncode != 0:
        logger.warning("playwright chromium install failed: %s", browser_install.stderr)
        raise BrowserError("browser_not_available")


def _limit_screenshot_b64(raw_b64: str) -> str:
    raw = base64.b64decode(raw_b64)
    if len(raw) <= manifest.MAX_SCREENSHOT_BYTES:
        return raw_b64
    # Réduction grossière : tronquer le binaire encodé (le front affiche un aperçu limité).
    max_raw = manifest.MAX_SCREENSHOT_BYTES
    truncated = raw[:max_raw]
    return base64.b64encode(truncated).decode("ascii")


class BrowserEngine:
    """Session chromium Playwright par répertoire plugin."""

    def __init__(self, plugin_data_dir: Path) -> None:
        self.plugin_data_dir = plugin_data_dir.expanduser().resolve()
        self.plugin_data_dir.mkdir(parents=True, exist_ok=True)
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None
        self._init_lock = asyncio.Lock()

    @property
    def active(self) -> bool:
        return self._page is not None

    @property
    def current_url(self) -> str:
        if self._page is None:
            return ""
        try:
            return str(self._page.url or "")
        except Exception:  # noqa: BLE001
            return ""

    @property
    def current_title(self) -> str:
        if self._page is None:
            return ""
        try:
            return str(self._page.title() or "")
        except Exception:  # noqa: BLE001
            return ""

    async def _ensure_ready(self, *, locale: str) -> None:
        async with self._init_lock:
            if self._page is not None:
                return
            ensure_playwright_installed(locale=locale)
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage"],
            )
            user_data = self.plugin_data_dir / "chromium-profile"
            user_data.mkdir(parents=True, exist_ok=True)
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "WorkprobaBrowser/1.0 (+https://improba.com; local automation)"
                ),
            )
            self._page = await self._context.new_page()
            self._page.set_default_timeout(manifest.ACTION_TIMEOUT_MS)

    async def _run_action(self, coro: Any) -> Any:
        try:
            return await asyncio.wait_for(coro, timeout=manifest.ACTION_TIMEOUT_MS / 1000)
        except TimeoutError as exc:
            raise BrowserError("browser_action_timeout") from exc

    async def _snapshot_payload(self) -> dict[str, str]:
        assert self._page is not None
        title = await self._run_action(self._page.title())
        url = self._page.url
        snapshot_yaml = await self._run_action(self._page.locator("body").aria_snapshot())
        screenshot_bytes = await self._run_action(
            self._page.screenshot(type="jpeg", quality=70, full_page=False)
        )
        screenshot_b64 = _limit_screenshot_b64(
            base64.b64encode(screenshot_bytes).decode("ascii")
        )
        return {
            "title": title,
            "url": url,
            "snapshot_yaml": snapshot_yaml,
            "screenshot_b64": screenshot_b64,
        }

    async def navigate(
        self,
        url: str,
        *,
        locale: str = "fr",
        audit_app_data: Path | None = None,
        audit_actor: str | None = None,
    ) -> dict[str, str]:
        target = validate_navigation_url(url)
        await self._ensure_ready(locale=locale)
        assert self._page is not None
        await self._run_action(self._page.goto(target, wait_until="domcontentloaded"))
        payload = await self._snapshot_payload()
        if audit_app_data is not None and audit_actor:
            from app.audit import log_event, resolve_app_data_dir

            log_event(
                resolve_app_data_dir(audit_app_data),
                "browser.navigate",
                audit_actor,
                {"url": payload.get("url"), "title": payload.get("title")},
            )
        return payload

    async def snapshot(self, *, locale: str = "fr") -> dict[str, str]:
        if not self.active:
            raise BrowserError("browser_session_inactive")
        await self._ensure_ready(locale=locale)
        return await self._snapshot_payload()

    async def click(self, ref: str, *, locale: str = "fr") -> dict[str, str]:
        if not ref.strip():
            raise BrowserError("browser_ref_missing")
        if not self.active:
            raise BrowserError("browser_session_inactive")
        await self._ensure_ready(locale=locale)
        assert self._page is not None
        locator = self._page.locator(f"aria-ref={ref.strip()}")
        await self._run_action(locator.click())
        return await self._snapshot_payload()

    async def type_text(self, ref: str, text: str, *, locale: str = "fr") -> dict[str, str]:
        if not ref.strip():
            raise BrowserError("browser_ref_missing")
        if not self.active:
            raise BrowserError("browser_session_inactive")
        await self._ensure_ready(locale=locale)
        assert self._page is not None
        locator = self._page.locator(f"aria-ref={ref.strip()}")
        await self._run_action(locator.fill(text))
        return await self._snapshot_payload()

    async def scroll(
        self,
        ref: str | None,
        direction: Literal["up", "down", "left", "right"],
        *,
        locale: str = "fr",
    ) -> dict[str, str]:
        if not self.active:
            raise BrowserError("browser_session_inactive")
        await self._ensure_ready(locale=locale)
        assert self._page is not None
        delta = {"up": (0, -400), "down": (0, 400), "left": (-400, 0), "right": (400, 0)}[
            direction
        ]
        if ref and ref.strip():
            locator = self._page.locator(f"aria-ref={ref.strip()}")
            await self._run_action(locator.scroll_into_view_if_needed())
        await self._run_action(
            self._page.mouse.wheel(delta[0], delta[1])
        )
        return await self._snapshot_payload()

    async def extract(
        self,
        selector: str,
        *,
        as_html: bool = False,
        locale: str = "fr",
    ) -> dict[str, Any]:
        if not selector.strip():
            raise BrowserError("browser_selector_missing")
        if not self.active:
            raise BrowserError("browser_session_inactive")
        await self._ensure_ready(locale=locale)
        assert self._page is not None
        locator = self._page.locator(selector.strip())
        if as_html:
            extracted = await self._run_action(locator.inner_html())
        else:
            extracted = await self._run_action(locator.inner_text())
        payload = await self._snapshot_payload()
        payload["extracted"] = extracted
        return payload

    async def press(self, key: str, *, locale: str = "fr") -> dict[str, str]:
        if not self.active:
            raise BrowserError("browser_session_inactive")
        await self._ensure_ready(locale=locale)
        assert self._page is not None
        await self._run_action(self._page.keyboard.press(key))
        return await self._snapshot_payload()

    async def back(self, *, locale: str = "fr") -> dict[str, str]:
        if not self.active:
            raise BrowserError("browser_session_inactive")
        await self._ensure_ready(locale=locale)
        assert self._page is not None
        await self._run_action(self._page.go_back(wait_until="domcontentloaded"))
        return await self._snapshot_payload()

    async def forward(self, *, locale: str = "fr") -> dict[str, str]:
        if not self.active:
            raise BrowserError("browser_session_inactive")
        await self._ensure_ready(locale=locale)
        assert self._page is not None
        await self._run_action(self._page.go_forward(wait_until="domcontentloaded"))
        return await self._snapshot_payload()

    async def close(self) -> None:
        await self._close_async()

    def close_sync(self) -> None:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._close_async())
            else:
                loop.run_until_complete(self._close_async())
        except RuntimeError:
            asyncio.run(self._close_async())

    async def _close_async(self) -> None:
        for attr in ("_page", "_context", "_browser"):
            resource = getattr(self, attr, None)
            if resource is not None:
                try:
                    await resource.close()
                except Exception:  # noqa: BLE001
                    pass
                setattr(self, attr, None)
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:  # noqa: BLE001
                pass
            self._playwright = None

    def status(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "url": self.current_url,
            "title": self.current_title,
        }


def browser_error_detail(code: str, locale: str) -> str:
    key = f"errors.{code}"
    message = t(locale, key)
    if message == key:
        return code
    return message
