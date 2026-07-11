"""Handlers de hooks minimaux pour le plugin projet (V2)."""

from __future__ import annotations

import logging
from typing import Any

from app.plugins.hooks import PluginContext

logger = logging.getLogger(__name__)


def on_space_opened(ctx: PluginContext, payload: dict[str, Any]) -> None:
    logger.debug(
        "workproba.projet space.opened space_id=%s",
        payload.get("space_id"),
    )


def on_file_written(ctx: PluginContext, payload: dict[str, Any]) -> None:
    logger.debug(
        "workproba.projet file.written path=%s by=%s",
        payload.get("path"),
        payload.get("by"),
    )


def on_tool_call_completed(ctx: PluginContext, payload: dict[str, Any]) -> None:
    if payload.get("tool") == "publish_artifact":
        logger.debug(
            "workproba.projet publish completed project_id=%s",
            (payload.get("result") or {}).get("project_id"),
        )


HANDLERS = {
    "space.opened": on_space_opened,
    "file.written": on_file_written,
    "tool.call_completed": on_tool_call_completed,
}
