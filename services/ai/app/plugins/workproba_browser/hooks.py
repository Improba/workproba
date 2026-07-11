"""Handlers de hooks pour le plugin browser (V2)."""

from __future__ import annotations

import logging
from typing import Any

from app.plugins.hooks import PluginContext

logger = logging.getLogger(__name__)


def on_browser_navigate(ctx: PluginContext, payload: dict[str, Any]) -> None:
    logger.debug(
        "workproba.browser browser.navigate url=%s title=%s",
        payload.get("url"),
        payload.get("title"),
    )


HANDLERS = {
    "browser.navigate": on_browser_navigate,
}
