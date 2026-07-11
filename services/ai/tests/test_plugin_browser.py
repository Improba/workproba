"""Tests plugin browser (engine mockée, endpoints, sécurité)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel

import app.auth as authmod
import app.main as mainmod
from app.agent.tools import ToolDeps, ToolContext, build_agent
from app.limits import DEFAULT_LIMITS
from app.plugins.workproba_browser import PLUGIN_ID, browser as browser_mod
from app.sandbox.runner import SandboxRunner

from conftest import FakeProjectClient


class MockBrowserEngine:
    """Moteur browser factice pour les tests (pas de chromium)."""

    def __init__(self, plugin_data_dir: Path) -> None:
        self.plugin_data_dir = plugin_data_dir
        self._active = False
        self._url = ""
        self._title = ""

    @property
    def active(self) -> bool:
        return self._active

    @property
    def current_url(self) -> str:
        return self._url

    @property
    def current_title(self) -> str:
        return self._title

    async def navigate(
        self,
        url: str,
        *,
        locale: str = "fr",
        audit_app_data: Path | None = None,
        audit_actor: str | None = None,
    ) -> dict[str, str]:
        _ = locale
        browser_mod.validate_navigation_url(url)
        self._active = True
        self._url = url
        self._title = "Mock Page"
        return self._snapshot()

    async def snapshot(self, *, locale: str = "fr") -> dict[str, str]:
        _ = locale
        if not self._active:
            raise browser_mod.BrowserError("browser_session_inactive")
        return self._snapshot()

    async def click(self, ref: str, *, locale: str = "fr") -> dict[str, str]:
        _ = locale
        if not ref.strip():
            raise browser_mod.BrowserError("browser_ref_missing")
        return await self.snapshot(locale=locale)

    async def type_text(self, ref: str, text: str, *, locale: str = "fr") -> dict[str, str]:
        _ = (ref, text, locale)
        return await self.snapshot()

    async def scroll(
        self,
        ref: str | None,
        direction: str,
        *,
        locale: str = "fr",
    ) -> dict[str, str]:
        _ = (ref, direction, locale)
        return await self.snapshot()

    async def extract(
        self,
        selector: str,
        *,
        as_html: bool = False,
        locale: str = "fr",
    ) -> dict[str, Any]:
        _ = (as_html, locale)
        if not selector.strip():
            raise browser_mod.BrowserError("browser_selector_missing")
        payload = await self.snapshot()
        payload["extracted"] = f"text from {selector}"
        return payload

    async def press(self, key: str, *, locale: str = "fr") -> dict[str, str]:
        _ = (key, locale)
        return await self.snapshot()

    async def back(self, *, locale: str = "fr") -> dict[str, str]:
        _ = locale
        return await self.snapshot()

    async def forward(self, *, locale: str = "fr") -> dict[str, str]:
        _ = locale
        return await self.snapshot()

    async def close(self) -> None:
        self._active = False
        self._url = ""
        self._title = ""

    def close_sync(self) -> None:
        self._active = False

    def status(self) -> dict[str, Any]:
        return {
            "active": self._active,
            "url": self._url,
            "title": self._title,
        }

    def _snapshot(self) -> dict[str, str]:
        return {
            "title": self._title,
            "url": self._url,
            "snapshot_yaml": "- heading: Mock\n  ref: e1",
            "screenshot_b64": "aGVsbG8=",
        }


@pytest.fixture(autouse=True)
def _mock_browser_engine() -> None:
    browser_mod.set_engine_factory(MockBrowserEngine)
    yield
    browser_mod.set_engine_factory(None)


@pytest.fixture(autouse=True)
def _patch_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)


@pytest.fixture
def plugin_dir(tmp_path: Path) -> Path:
    path = tmp_path / "plugins" / PLUGIN_ID
    path.mkdir(parents=True)
    return path


def test_validate_url_rejects_dangerous_schemes() -> None:
    with pytest.raises(browser_mod.BrowserError) as exc:
        browser_mod.validate_navigation_url("file:///etc/passwd")
    assert str(exc.value) == "browser_url_scheme_forbidden"

    with pytest.raises(browser_mod.BrowserError):
        browser_mod.validate_navigation_url("javascript:alert(1)")

    assert (
        browser_mod.validate_navigation_url("https://example.com/page")
        == "https://example.com/page"
    )


def test_browser_endpoints_navigate_and_status(plugin_dir: Path) -> None:
    headers = {"X-Internal-Secret": "desktop-dev-secret"}
    with TestClient(mainmod.app) as client:
        status = client.get(
            "/plugins/browser/status",
            params={"plugin_data_dir": str(plugin_dir)},
            headers=headers,
        )
        assert status.status_code == 200
        assert status.json()["active"] is False

        nav = client.post(
            "/plugins/browser/navigate",
            json={
                "plugin_data_dir": str(plugin_dir),
                "url": "https://example.com",
            },
            headers=headers,
        )
        assert nav.status_code == 200
        body = nav.json()
        assert body["url"] == "https://example.com"
        assert "snapshot_yaml" in body
        assert body["screenshot_b64"]

        status2 = client.get(
            "/plugins/browser/status",
            params={"plugin_data_dir": str(plugin_dir)},
            headers=headers,
        )
        assert status2.json()["active"] is True

        action = client.post(
            "/plugins/browser/action",
            json={
                "plugin_data_dir": str(plugin_dir),
                "action": "extract",
                "selector": "h1",
            },
            headers=headers,
        )
        assert action.status_code == 200
        assert action.json()["extracted"] == "text from h1"

        close = client.post(
            "/plugins/browser/close",
            json={"plugin_data_dir": str(plugin_dir)},
            headers=headers,
        )
        assert close.status_code == 200
        assert close.json()["ok"] is True


def test_browser_navigate_rejects_forbidden_scheme(plugin_dir: Path) -> None:
    with TestClient(mainmod.app) as client:
        resp = client.post(
            "/plugins/browser/navigate",
            json={
                "plugin_data_dir": str(plugin_dir),
                "url": "file:///secret",
            },
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert resp.status_code == 400


def test_browser_locked_mode_blocks_navigation(plugin_dir: Path) -> None:
    with TestClient(mainmod.app) as client:
        resp = client.post(
            "/plugins/browser/navigate",
            json={
                "plugin_data_dir": str(plugin_dir),
                "url": "https://example.com",
                "settings_locked": True,
                "permissions_network": False,
            },
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert resp.status_code == 403


def test_browser_endpoints_require_secret(plugin_dir: Path) -> None:
    with TestClient(mainmod.app) as client:
        resp = client.get(
            "/plugins/browser/status",
            params={"plugin_data_dir": str(plugin_dir)},
        )
        assert resp.status_code == 401


def test_plugin_tools_hidden_without_active_plugins() -> None:
    agent = build_agent(TestModel())
    names = sorted(agent._function_toolset.tools.keys())
    assert "browser_navigate" not in names


def test_plugin_tools_registered_when_active() -> None:
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_ID])
    names = sorted(agent._function_toolset.tools.keys())
    assert "browser_navigate" in names
    assert "browser_click" in names
    assert "browser_extract" in names


@pytest.mark.asyncio
async def test_browser_navigate_tool_returns_snapshot(plugin_dir: Path) -> None:
    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s1",
            documents=[],
            plugin_data_dir=plugin_dir,
            locale="fr",
            active_plugins=[PLUGIN_ID],
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
    )
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_ID])
    tool = agent._function_toolset.tools["browser_navigate"]
    ctx = RunContext(deps=deps, model=TestModel(), usage=None, prompt=None, tool_call_id="tc1")
    result = await tool.function(ctx, url="https://example.com/pricing")
    assert result["url"] == "https://example.com/pricing"
    assert result["snapshot_yaml"]
    assert result["human_summary"]


@pytest.mark.asyncio
async def test_browser_navigate_tool_blocked_in_locked_mode(plugin_dir: Path) -> None:
    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s1",
            documents=[],
            plugin_data_dir=plugin_dir,
            locale="fr",
            active_plugins=[PLUGIN_ID],
            settings_locked=True,
            permissions_network=False,
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
    )
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_ID])
    tool = agent._function_toolset.tools["browser_navigate"]
    ctx = RunContext(deps=deps, model=TestModel(), usage=None, prompt=None, tool_call_id="tc1")
    with pytest.raises(Exception) as exc:
        await tool.function(ctx, url="https://example.com")
    assert "verrouillé" in str(exc.value).lower() or "locked" in str(exc.value).lower()
