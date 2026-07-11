"""Dispatch synchrone des hooks core vers les plugins enregistrés (V2)."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.schemas import ProviderSet

logger = logging.getLogger(__name__)

HookHandler = Callable[["PluginContext", dict[str, Any]], None]

CORE_HOOK_EVENTS = frozenset(
    {
        "space.opened",
        "space.closed",
        "file.written",
        "file.deleted",
        "message.sent",
        "turn.started",
        "turn.completed",
        "tool.call_started",
        "tool.call_completed",
        "attachment.ignored",
        "provider_set.changed",
        "plugin.activated",
        "plugin.deactivated",
    }
)


@dataclass(frozen=True)
class PluginContext:
    """Contexte passé aux handlers de hooks côté sidecar."""

    plugin_id: str
    plugin_data_dir: Path
    locale: str
    provider_set: ProviderSet | None
    permissions: frozenset[str] = field(default_factory=frozenset)
    workspace_data_dir: Path | None = None
    project_root: Path | None = None


class HookRegistry:
    """Registre des handlers par plugin et par événement."""

    def __init__(self) -> None:
        self._handlers: dict[str, dict[str, list[HookHandler]]] = defaultdict(
            lambda: defaultdict(list)
        )

    def subscribe(
        self,
        plugin_id: str,
        event: str,
        handler: HookHandler,
    ) -> None:
        if event not in CORE_HOOK_EVENTS:
            logger.debug("Unknown hook event %s for plugin %s (ignored)", event, plugin_id)
        self._handlers[plugin_id][event].append(handler)

    def unsubscribe_plugin(self, plugin_id: str) -> None:
        self._handlers.pop(plugin_id, None)

    def dispatch(self, event: str, payload: dict[str, Any]) -> None:
        """Dispatch synchrone à tous les plugins abonnés à l'événement."""
        if event not in CORE_HOOK_EVENTS:
            logger.debug("Dispatch to unknown hook event: %s", event)
        for plugin_id, events in self._handlers.items():
            handlers = events.get(event, [])
            ctx = payload.get("_plugin_contexts", {}).get(plugin_id)
            if ctx is None:
                continue
            for handler in handlers:
                try:
                    handler(ctx, payload)
                except Exception:
                    logger.exception(
                        "Hook handler failed (plugin=%s event=%s)",
                        plugin_id,
                        event,
                    )


hook_registry = HookRegistry()
