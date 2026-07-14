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
from app.audit import read_audit, resolve_app_data_dir
from app.limits import DEFAULT_LIMITS
from app.plugins.workproba_browser import PLUGIN_ID, browser as browser_mod
from app.plugins.workproba_browser import manifest as browser_manifest
from app.sandbox.runner import SandboxRunner

from conftest import FakeProjectClient


class MockBrowserEngine:
    """Moteur browser factice pour les tests (pas de chromium)."""

    def __init__(self, plugin_data_dir: Path) -> None:
        self.plugin_data_dir = plugin_data_dir
        self._active = False
        self._url = ""
        self._title = ""
        self._last_ui_snapshot: dict[str, Any] | None = None

    @property
    def last_ui_snapshot(self) -> dict[str, Any] | None:
        return self._last_ui_snapshot

    def remember_tool_ui_snapshot(self, payload: dict[str, Any]) -> None:
        self._last_tool_ui_snapshot = {
            key: payload[key]
            for key in ("screenshot_b64", "action_ref", "action_bbox", "viewport")
            if key in payload and payload.get(key) is not None
        }

    @property
    def last_tool_ui_snapshot(self) -> dict[str, Any] | None:
        return self._last_tool_ui_snapshot

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
        work_id: str | None = None,
    ) -> dict[str, str]:
        _ = (locale, work_id)
        browser_mod.validate_navigation_url(url)
        self._active = True
        self._url = url
        self._title = "Mock Page"
        if audit_app_data is not None and audit_actor:
            from app.audit import log_event, resolve_app_data_dir

            log_event(
                resolve_app_data_dir(audit_app_data),
                "browser.navigate",
                audit_actor,
                {"url": self._url, "title": self._title},
            )
        return self._snapshot()

    async def snapshot(
        self,
        *,
        locale: str = "fr",
        action_ref: str | None = None,
    ) -> dict[str, Any]:
        _ = locale
        if not self._active:
            raise browser_mod.BrowserError("browser_session_inactive")
        return self._snapshot(action_ref=action_ref)

    async def click(self, ref: str, *, locale: str = "fr") -> dict[str, Any]:
        _ = locale
        if not ref.strip():
            raise browser_mod.BrowserError("browser_ref_missing")
        return await self.snapshot(locale=locale, action_ref=ref)

    async def type_text(self, ref: str, text: str, *, locale: str = "fr") -> dict[str, Any]:
        _ = (text, locale)
        return await self.snapshot(locale=locale, action_ref=ref)

    async def scroll(
        self,
        ref: str | None,
        direction: str,
        *,
        locale: str = "fr",
    ) -> dict[str, Any]:
        _ = direction
        return await self.snapshot(locale=locale, action_ref=ref)

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

    def remember_tool_ui_snapshot(self, payload: dict[str, Any]) -> None:
        self._last_tool_ui_snapshot = {
            key: payload[key]
            for key in ("screenshot_b64", "action_ref", "action_bbox", "viewport")
            if key in payload and payload.get(key) is not None
        }

    @property
    def last_tool_ui_snapshot(self) -> dict[str, Any] | None:
        return self._last_tool_ui_snapshot

    def status(self) -> dict[str, Any]:
        return {
            "active": self._active,
            "url": self._url,
            "title": self._title,
        }

    def _snapshot(self, *, action_ref: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "title": self._title,
            "url": self._url,
            "snapshot_yaml": "- heading: Mock\n  ref: e1",
            "screenshot_b64": "aGVsbG8=",
            "viewport": browser_mod.viewport_payload(),
        }
        if action_ref:
            payload["action_ref"] = action_ref
            payload["action_bbox"] = {
                "x": 10.0,
                "y": 20.0,
                "width": 100.0,
                "height": 32.0,
            }
        self._last_ui_snapshot = dict(payload)
        return payload


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
    for tool_name in browser_manifest.TOOLS:
        assert tool_name in names


def test_manifest_tools_matches_registered_agent_tools() -> None:
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_ID])
    registered = {
        name
        for name in agent._function_toolset.tools
        if name.startswith("browser_")
    }
    assert registered == set(browser_manifest.TOOLS)


def test_manifest_tools_matches_front_browser_tools_list() -> None:
    """Alignement avec front/src/utils/browserTools.ts (liste statique)."""
    front_tools = {
        "browser_navigate",
        "browser_click",
        "browser_extract",
        "browser_type",
        "browser_scroll",
        "browser_press",
        "browser_back",
        "browser_forward",
    }
    assert set(browser_manifest.TOOLS) == front_tools


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


def _browser_tool_deps(
    plugin_dir: Path,
    *,
    workspace_data_dir: Path | None = None,
    settings_locked: bool = False,
    permissions_network: bool = True,
    browser_pilotage_paused: bool = False,
) -> ToolDeps:
    return ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s1",
            documents=[],
            plugin_data_dir=plugin_dir,
            locale="fr",
            active_plugins=[PLUGIN_ID],
            workspace_data_dir=workspace_data_dir,
            settings_locked=settings_locked,
            permissions_network=permissions_network,
            browser_pilotage_paused=browser_pilotage_paused,
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
    )


def _browser_run_context(deps: ToolDeps) -> RunContext[Any]:
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_ID])
    return RunContext(deps=deps, model=TestModel(), usage=None, prompt=None, tool_call_id="tc1")


@pytest.mark.asyncio
async def test_browser_navigate_tool_writes_audit_log(
    plugin_dir: Path, tmp_path: Path
) -> None:
    app_data = tmp_path / "app_data"
    workspace = app_data / "spaces" / "space-1" / "project"
    workspace.mkdir(parents=True)
    deps = _browser_tool_deps(plugin_dir, workspace_data_dir=workspace)
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_ID])
    tool = agent._function_toolset.tools["browser_navigate"]
    ctx = RunContext(deps=deps, model=TestModel(), usage=None, prompt=None, tool_call_id="tc1")
    await tool.function(ctx, url="https://example.com/pricing")

    entries, total = read_audit(
        resolve_app_data_dir(workspace),
        event="browser.navigate",
    )
    assert total == 1
    assert entries[0]["actor"] == "agent"
    assert entries[0]["details"]["url"] == "https://example.com/pricing"


@pytest.mark.asyncio
async def test_browser_click_tool_returns_snapshot(plugin_dir: Path) -> None:
    deps = _browser_tool_deps(plugin_dir)
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_ID])
    navigate = agent._function_toolset.tools["browser_navigate"]
    ctx = _browser_run_context(deps)
    await navigate.function(ctx, url="https://example.com")
    click = agent._function_toolset.tools["browser_click"]
    result = await click.function(ctx, ref="e1")
    assert result["snapshot_yaml"]
    assert result["human_summary"]


@pytest.mark.asyncio
async def test_browser_type_tool_returns_snapshot(plugin_dir: Path) -> None:
    deps = _browser_tool_deps(plugin_dir)
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_ID])
    ctx = _browser_run_context(deps)
    await agent._function_toolset.tools["browser_navigate"].function(
        ctx, url="https://example.com"
    )
    result = await agent._function_toolset.tools["browser_type"].function(
        ctx, ref="e2", text="hello@example.com"
    )
    assert result["snapshot_yaml"]
    assert result["human_summary"]


@pytest.mark.asyncio
async def test_browser_scroll_tool_without_ref(plugin_dir: Path) -> None:
    deps = _browser_tool_deps(plugin_dir)
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_ID])
    ctx = _browser_run_context(deps)
    await agent._function_toolset.tools["browser_navigate"].function(
        ctx, url="https://example.com"
    )
    result = await agent._function_toolset.tools["browser_scroll"].function(
        ctx, direction="down"
    )
    assert result["snapshot_yaml"]


@pytest.mark.asyncio
async def test_browser_press_tool_enter(plugin_dir: Path) -> None:
    deps = _browser_tool_deps(plugin_dir)
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_ID])
    ctx = _browser_run_context(deps)
    await agent._function_toolset.tools["browser_navigate"].function(
        ctx, url="https://example.com"
    )
    result = await agent._function_toolset.tools["browser_press"].function(ctx, key="Enter")
    assert "screenshot_b64" not in result
    assert browser_mod.get_engine(plugin_dir).last_ui_snapshot["screenshot_b64"]


@pytest.mark.asyncio
async def test_browser_back_tool(plugin_dir: Path) -> None:
    deps = _browser_tool_deps(plugin_dir)
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_ID])
    ctx = _browser_run_context(deps)
    await agent._function_toolset.tools["browser_navigate"].function(
        ctx, url="https://example.com"
    )
    result = await agent._function_toolset.tools["browser_back"].function(ctx)
    assert result["url"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name,kwargs",
    [
        ("browser_navigate", {"url": "https://example.com"}),
        ("browser_click", {"ref": "e1"}),
        ("browser_extract", {"selector": "h1"}),
        ("browser_type", {"ref": "e1", "text": "x"}),
        ("browser_scroll", {"direction": "down"}),
        ("browser_press", {"key": "Enter"}),
        ("browser_back", {}),
        ("browser_forward", {}),
    ],
)
async def test_browser_tools_blocked_in_locked_mode(
    plugin_dir: Path,
    tool_name: str,
    kwargs: dict[str, Any],
) -> None:
    deps = _browser_tool_deps(
        plugin_dir,
        settings_locked=True,
        permissions_network=False,
    )
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_ID])
    tool = agent._function_toolset.tools[tool_name]
    ctx = _browser_run_context(deps)
    with pytest.raises(Exception) as exc:
        await tool.function(ctx, **kwargs)
    assert "verrouillé" in str(exc.value).lower() or "locked" in str(exc.value).lower()


def test_browser_action_type_updates_snapshot(plugin_dir: Path) -> None:
    headers = {"X-Internal-Secret": "desktop-dev-secret"}
    with TestClient(mainmod.app) as client:
        client.post(
            "/plugins/browser/navigate",
            json={"plugin_data_dir": str(plugin_dir), "url": "https://example.com"},
            headers=headers,
        )
        resp = client.post(
            "/plugins/browser/action",
            json={
                "plugin_data_dir": str(plugin_dir),
                "action": "type",
                "ref": "e1",
                "text": "hello",
            },
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["snapshot_yaml"]


def test_browser_action_scroll(plugin_dir: Path) -> None:
    headers = {"X-Internal-Secret": "desktop-dev-secret"}
    with TestClient(mainmod.app) as client:
        client.post(
            "/plugins/browser/navigate",
            json={"plugin_data_dir": str(plugin_dir), "url": "https://example.com"},
            headers=headers,
        )
        resp = client.post(
            "/plugins/browser/action",
            json={
                "plugin_data_dir": str(plugin_dir),
                "action": "scroll",
                "direction": "down",
            },
            headers=headers,
        )
        assert resp.status_code == 200


def test_browser_action_click_rejects_empty_ref(plugin_dir: Path) -> None:
    headers = {"X-Internal-Secret": "desktop-dev-secret"}
    with TestClient(mainmod.app) as client:
        client.post(
            "/plugins/browser/navigate",
            json={"plugin_data_dir": str(plugin_dir), "url": "https://example.com"},
            headers=headers,
        )
        resp = client.post(
            "/plugins/browser/action",
            json={"plugin_data_dir": str(plugin_dir), "action": "click"},
            headers=headers,
        )
        assert resp.status_code == 400


def test_browser_action_unknown_action_400(plugin_dir: Path) -> None:
    headers = {"X-Internal-Secret": "desktop-dev-secret"}
    with TestClient(mainmod.app) as client:
        client.post(
            "/plugins/browser/navigate",
            json={"plugin_data_dir": str(plugin_dir), "url": "https://example.com"},
            headers=headers,
        )
        resp = client.post(
            "/plugins/browser/action",
            json={"plugin_data_dir": str(plugin_dir), "action": "not-a-real-action"},
            headers=headers,
        )
        assert resp.status_code == 422


def test_browser_session_inactive_returns_409(plugin_dir: Path) -> None:
    headers = {"X-Internal-Secret": "desktop-dev-secret"}
    with TestClient(mainmod.app) as client:
        resp = client.post(
            "/plugins/browser/action",
            json={
                "plugin_data_dir": str(plugin_dir),
                "action": "click",
                "ref": "e1",
            },
            headers=headers,
        )
        assert resp.status_code == 409


def test_limit_screenshot_b64_omits_over_max() -> None:
    import base64

    from app.plugins.workproba_browser import manifest as browser_manifest_mod

    oversized = b"x" * (browser_manifest_mod.MAX_SCREENSHOT_BYTES + 1000)
    raw_b64 = base64.b64encode(oversized).decode("ascii")
    assert browser_mod._limit_screenshot_b64(raw_b64) == ""


def test_limit_screenshot_b64_keeps_small_payload() -> None:
    import base64

    small = b"hello"
    raw_b64 = base64.b64encode(small).decode("ascii")
    assert browser_mod._limit_screenshot_b64(raw_b64) == raw_b64


@pytest.mark.asyncio
async def test_browser_navigate_blocked_when_pilotage_paused(plugin_dir: Path) -> None:
    deps = _browser_tool_deps(plugin_dir, browser_pilotage_paused=True)
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_ID])
    tool = agent._function_toolset.tools["browser_navigate"]
    ctx = _browser_run_context(deps)
    with pytest.raises(Exception) as exc:
        await tool.function(ctx, url="https://example.com")
    assert "pilotage" in str(exc.value).lower() or "piloting" in str(exc.value).lower()


def test_browser_action_click_includes_bbox(plugin_dir: Path) -> None:
    headers = {"X-Internal-Secret": "desktop-dev-secret"}
    with TestClient(mainmod.app) as client:
        client.post(
            "/plugins/browser/navigate",
            json={"plugin_data_dir": str(plugin_dir), "url": "https://example.com"},
            headers=headers,
        )
        resp = client.post(
            "/plugins/browser/action",
            json={
                "plugin_data_dir": str(plugin_dir),
                "action": "click",
                "ref": "e1",
            },
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["action_ref"] == "e1"
        assert body["action_bbox"]["width"] == 100.0
        assert body["viewport"]["width"] == browser_mod.viewport_payload()["width"]


@pytest.mark.asyncio
async def test_browser_click_tool_includes_action_bbox(plugin_dir: Path) -> None:
    deps = _browser_tool_deps(plugin_dir)
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_ID])
    ctx = _browser_run_context(deps)
    await agent._function_toolset.tools["browser_navigate"].function(
        ctx, url="https://example.com"
    )
    result = await agent._function_toolset.tools["browser_click"].function(ctx, ref="e1")
    assert result["action_ref"] == "e1"
    assert result["action_bbox"]["x"] == 10.0
    assert result["viewport"]["height"] == browser_mod.viewport_payload()["height"]
    assert "screenshot_b64" not in result


def test_enrich_browser_tool_result_for_sse_injects_screenshot(plugin_dir: Path) -> None:
    engine = browser_mod.get_engine(plugin_dir)
    engine.remember_tool_ui_snapshot({"screenshot_b64": "aGVsbG8="})
    model_result = {"snapshot_yaml": "- heading: Mock", "url": "https://example.com"}
    enriched = browser_mod.enrich_browser_tool_result_for_sse(
        "browser_click",
        model_result,
        plugin_dir,
    )
    assert enriched["screenshot_b64"] == "aGVsbG8="
    assert "screenshot_b64" not in model_result


def test_enrich_browser_tool_result_resolves_plugins_root(plugin_dir: Path) -> None:
    plugins_root = plugin_dir.parent
    engine = browser_mod.get_engine(plugin_dir)
    engine.remember_tool_ui_snapshot({"screenshot_b64": "aGVsbG8="})
    enriched = browser_mod.enrich_browser_tool_result_for_sse(
        "browser_navigate",
        {"url": "https://example.com"},
        plugins_root,
    )
    assert enriched["screenshot_b64"] == "aGVsbG8="


@pytest.mark.asyncio
async def test_browser_navigate_excludes_screenshot_from_model_result(plugin_dir: Path) -> None:
    deps = _browser_tool_deps(plugin_dir)
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_ID])
    ctx = _browser_run_context(deps)
    result = await agent._function_toolset.tools["browser_navigate"].function(
        ctx, url="https://example.com"
    )
    assert "screenshot_b64" not in result
    assert browser_mod.get_engine(plugin_dir).last_ui_snapshot["screenshot_b64"]
