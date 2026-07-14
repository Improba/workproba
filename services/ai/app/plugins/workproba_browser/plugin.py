"""Outils agent du plugin browser."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ModelRetry

from app.agent.human import build_human_summary
from app.audit import resolve_app_data_dir
from app.plugins.hooks import PluginContext
from app.plugins.registry import PLUGIN_WORKPROBA_BROWSER, resolve_plugin_data_dir
from app.plugins.workproba_browser import browser as browser_engine
from app.plugins.workproba_browser import manifest
from app.plugins.workproba_browser.hooks import on_browser_navigate


def _plugin_data_dir(ctx: RunContext[Any]) -> Path:
    data_dir = resolve_plugin_data_dir(
        PLUGIN_WORKPROBA_BROWSER,
        ctx.deps.context.plugin_data_dir,
    )
    if data_dir is None:
        raise ModelRetry("Plugin browser: plugin_data_dir manquant")
    return data_dir


def _assert_browser_allowed(ctx: RunContext[Any]) -> None:
    if ctx.deps.context.browser_pilotage_paused:
        raise ModelRetry(
            browser_engine.browser_error_detail(
                "browser_pilotage_paused",
                ctx.deps.context.locale,
            )
        )
    if (
        ctx.deps.context.settings_locked
        and not ctx.deps.context.permissions_network
    ):
        raise ModelRetry(
            browser_engine.browser_error_detail("browser_locked", ctx.deps.context.locale)
        )


def _emit_navigate_hook(ctx: RunContext[Any], payload: dict[str, Any]) -> None:
    data_dir = ctx.deps.context.plugin_data_dir
    if data_dir is None:
        return
    plugin_ctx = PluginContext(
        plugin_id="workproba.browser",
        plugin_data_dir=data_dir,
        locale=ctx.deps.context.locale,
        provider_set=ctx.deps.context.provider_set,
    )
    on_browser_navigate(plugin_ctx, payload)


def _retry_browser_error(exc: browser_engine.BrowserError, locale: str) -> ModelRetry:
    return ModelRetry(browser_engine.browser_error_detail(str(exc), locale))


def _snapshot_tool_result(
    tool_name: str,
    arguments: dict[str, Any],
    result: dict[str, Any],
    locale: str,
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "snapshot_yaml": result.get("snapshot_yaml"),
        "title": result.get("title"),
        "url": result.get("url"),
        "human_summary": build_human_summary(
            tool_name,
            arguments,
            result=result,
            locale=locale,
        ),
    }
    for key in ("action_ref", "action_bbox", "viewport"):
        if key in result and result.get(key) is not None:
            payload[key] = result.get(key)
    if extra:
        payload.update(extra)
    return payload


async def _run_browser_action(
    ctx: RunContext[Any],
    runner: Any,
) -> dict[str, Any]:
    locale = ctx.deps.context.locale
    _assert_browser_allowed(ctx)
    engine = browser_engine.get_engine(_plugin_data_dir(ctx))
    try:
        result = await runner(engine)
    except browser_engine.BrowserError as exc:
        raise _retry_browser_error(exc, locale) from exc
    except Exception as exc:  # noqa: BLE001
        raise ModelRetry(f"{type(exc).__name__}: {exc}") from exc
    engine.remember_tool_ui_snapshot(result)
    return result


def register_browser_tools(agent: Agent[Any, str]) -> None:
    @agent.tool
    async def browser_navigate(ctx: RunContext[Any], url: str) -> dict[str, Any]:
        """Navigate the embedded browser to a URL and return an accessibility snapshot.

        The LLM receives the textual snapshot; the screenshot is shown in the UI panel.

        Args:
            url: Target URL (http or https only).
        """
        locale = ctx.deps.context.locale
        _assert_browser_allowed(ctx)
        engine = browser_engine.get_engine(_plugin_data_dir(ctx))
        audit_app_data = (
            resolve_app_data_dir(ctx.deps.context.workspace_data_dir)
            if ctx.deps.context.workspace_data_dir is not None
            else None
        )
        try:
            result = await engine.navigate(
                url,
                locale=locale,
                audit_app_data=audit_app_data,
                audit_actor="agent" if audit_app_data is not None else None,
            )
        except browser_engine.BrowserError as exc:
            raise _retry_browser_error(exc, locale) from exc
        except Exception as exc:  # noqa: BLE001
            raise ModelRetry(f"{type(exc).__name__}: {exc}") from exc

        _emit_navigate_hook(
            ctx,
            {"url": result.get("url"), "title": result.get("title")},
        )
        engine.remember_tool_ui_snapshot(result)
        return {
            "title": result.get("title"),
            "url": result.get("url"),
            "snapshot_yaml": result.get("snapshot_yaml"),
            "viewport": result.get("viewport"),
            "human_summary": build_human_summary(
                "browser_navigate",
                {"url": url},
                result=result,
                locale=locale,
            ),
        }

    @agent.tool
    async def browser_click(ctx: RunContext[Any], ref: str) -> dict[str, Any]:
        """Click an element in the browser by accessibility ref from the snapshot.

        Args:
            ref: Element ref from snapshot_yaml (e.g. e42).
        """
        locale = ctx.deps.context.locale
        result = await _run_browser_action(
            ctx,
            lambda engine: engine.click(ref, locale=locale),
        )
        return _snapshot_tool_result("browser_click", {"ref": ref}, result, locale)

    @agent.tool
    async def browser_extract(ctx: RunContext[Any], selector: str) -> dict[str, Any]:
        """Extract text from the current page using a CSS selector.

        Args:
            selector: CSS selector for the target element.
        """
        locale = ctx.deps.context.locale
        result = await _run_browser_action(
            ctx,
            lambda engine: engine.extract(selector, locale=locale),
        )
        return _snapshot_tool_result(
            "browser_extract",
            {"selector": selector},
            result,
            locale,
            extra={"extracted": result.get("extracted")},
        )

    @agent.tool
    async def browser_type(ctx: RunContext[Any], ref: str, text: str) -> dict[str, Any]:
        """Type text into an input element by accessibility ref from the snapshot.

        Args:
            ref: Element ref from snapshot_yaml (e.g. e42).
            text: Text to enter into the field.
        """
        locale = ctx.deps.context.locale
        result = await _run_browser_action(
            ctx,
            lambda engine: engine.type_text(ref, text, locale=locale),
        )
        return _snapshot_tool_result("browser_type", {"ref": ref, "text": text}, result, locale)

    @agent.tool
    async def browser_scroll(
        ctx: RunContext[Any],
        direction: Literal["up", "down", "left", "right"],
        ref: str | None = None,
    ) -> dict[str, Any]:
        """Scroll the page or bring an element into view.

        Args:
            direction: Scroll direction.
            ref: Optional element ref to scroll into view first.
        """
        locale = ctx.deps.context.locale
        result = await _run_browser_action(
            ctx,
            lambda engine: engine.scroll(ref, direction, locale=locale),
        )
        return _snapshot_tool_result(
            "browser_scroll",
            {"direction": direction, "ref": ref or ""},
            result,
            locale,
        )

    @agent.tool
    async def browser_press(ctx: RunContext[Any], key: str) -> dict[str, Any]:
        """Press a keyboard key in the browser (e.g. Enter, Tab, Escape).

        Args:
            key: Key name understood by Playwright (Enter, Tab, Escape, etc.).
        """
        locale = ctx.deps.context.locale
        result = await _run_browser_action(
            ctx,
            lambda engine: engine.press(key, locale=locale),
        )
        return _snapshot_tool_result("browser_press", {"key": key}, result, locale)

    @agent.tool
    async def browser_back(ctx: RunContext[Any]) -> dict[str, Any]:
        """Go back to the previous page in browser history."""
        locale = ctx.deps.context.locale
        result = await _run_browser_action(
            ctx,
            lambda engine: engine.back(locale=locale),
        )
        return _snapshot_tool_result("browser_back", {}, result, locale)

    @agent.tool
    async def browser_forward(ctx: RunContext[Any]) -> dict[str, Any]:
        """Go forward to the next page in browser history."""
        locale = ctx.deps.context.locale
        result = await _run_browser_action(
            ctx,
            lambda engine: engine.forward(locale=locale),
        )
        return _snapshot_tool_result("browser_forward", {}, result, locale)

    _ = manifest  # référence manifeste outils
