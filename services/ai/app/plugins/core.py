"""API core exposée aux plugins Python (wrappers sur l'existant)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.audit import log_event, resolve_app_data_dir
from app.i18n import format_summary, t
from app.plugins.hooks import PluginContext, hook_registry
from app.rag.store import RagStore
from app.schemas import ProviderSet

logger = logging.getLogger(__name__)

_CROSS_AUDIT_LOG: list[dict[str, Any]] = []


def cross_audit_log() -> list[dict[str, Any]]:
    """Journal des accès cross-namespace (tests / audit)."""
    return list(_CROSS_AUDIT_LOG)


def clear_cross_audit_log() -> None:
    _CROSS_AUDIT_LOG.clear()


class CoreStorage:
    def __init__(self, ctx: PluginContext) -> None:
        self._ctx = ctx
        self._data_file = ctx.plugin_data_dir / "data.json"

    def path(self) -> Path:
        return self._ctx.plugin_data_dir

    def _load_data(self) -> dict[str, Any]:
        if not self._data_file.is_file():
            return {}
        try:
            with self._data_file.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
            return raw if isinstance(raw, dict) else {}
        except Exception:
            return {}

    def _save_data(self, data: dict[str, Any]) -> None:
        self._ctx.plugin_data_dir.mkdir(parents=True, exist_ok=True)
        with self._data_file.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)

    def get(self, key: str) -> Any:
        return self._load_data().get(key)

    def set(self, key: str, val: Any) -> None:
        data = self._load_data()
        data[key] = val
        self._save_data(data)

    def cross(
        self,
        target: str,
        op: str,
        key: str,
        value: Any = None,
    ) -> Any:
        permission = f"storage:cross:{target}"
        if permission not in self._ctx.permissions:
            raise PermissionError(f"Missing permission: {permission}")

        target_dir = self._ctx.plugin_data_dir.parent / target
        target_file = target_dir / "data.json"
        entry = {
            "source_plugin": self._ctx.plugin_id,
            "target": target,
            "op": op,
            "key": key,
        }
        _CROSS_AUDIT_LOG.append(entry)
        logger.info("storage.cross audit: %s", entry)
        app_data = resolve_app_data_dir(self._ctx.plugin_data_dir.parent)
        log_event(
            app_data,
            "plugin.cross",
            f"plugin:{self._ctx.plugin_id}",
            {"target": target, "op": op, "key": key},
        )

        if op == "get":
            if not target_file.is_file():
                return None
            with target_file.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
            return raw.get(key) if isinstance(raw, dict) else None

        if op == "set":
            target_dir.mkdir(parents=True, exist_ok=True)
            data: dict[str, Any] = {}
            if target_file.is_file():
                with target_file.open("r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
                if isinstance(loaded, dict):
                    data = loaded
            data[key] = value
            with target_file.open("w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
            return True

        raise ValueError(f"Unsupported cross op: {op}")


class CoreI18n:
    def __init__(self, ctx: PluginContext) -> None:
        self._locale = ctx.locale

    def t(self, key: str, **vars: Any) -> str:
        return t(self._locale, key, **vars)

    def format(self, key: str, vars: dict[str, Any] | None = None, count: int = 0) -> str:
        return format_summary(self._locale, key, vars, count)


class CoreProviders:
    def __init__(self, provider_set: ProviderSet | None) -> None:
        self._provider_set = provider_set

    def llm(self) -> ProviderSet | None:
        return self._provider_set

    def active_set(self) -> ProviderSet | None:
        return self._provider_set


class CoreMemory:
    def __init__(self, rag_store: RagStore | None) -> None:
        self._rag_store = rag_store

    async def search(self, query: str, k: int = 8) -> list[dict[str, Any]]:
        if self._rag_store is None:
            return []
        return await self._rag_store.search(query=query, limit=k)


class CoreHooks:
    def emit(self, event: str, payload: dict[str, Any]) -> None:
        hook_registry.dispatch(event, payload)


@dataclass
class CoreAPI:
    """Facade API core pour un plugin actif."""

    ctx: PluginContext
    storage: CoreStorage = field(init=False)
    i18n: CoreI18n = field(init=False)
    providers: CoreProviders = field(init=False)
    memory: CoreMemory = field(init=False)
    hooks: CoreHooks = field(init=False)

    def __post_init__(self) -> None:
        self.storage = CoreStorage(self.ctx)
        self.i18n = CoreI18n(self.ctx)
        self.providers = CoreProviders(self.ctx.provider_set)
        self.memory = CoreMemory(self._rag_store)
        self.hooks = CoreHooks()

    _rag_store: RagStore | None = field(default=None, repr=False)

    @classmethod
    def for_plugin(
        cls,
        ctx: PluginContext,
        *,
        rag_store: RagStore | None = None,
    ) -> CoreAPI:
        api = cls(ctx=ctx)
        api._rag_store = rag_store
        api.memory = CoreMemory(rag_store)
        return api
