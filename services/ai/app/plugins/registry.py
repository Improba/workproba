"""Registre des plugins builtin V2 et enregistrement des outils agent."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic_ai import Agent

from app.plugins.hooks import PluginContext, hook_registry
from app.plugins.workproba_projet import manifest as projet_manifest
from app.plugins.workproba_projet import hooks as projet_hooks
from app.plugins.workproba_personas import manifest as personas_manifest
from app.plugins.workproba_browser import manifest as browser_manifest
from app.plugins.workproba_cloud import manifest as cloud_manifest

PLUGIN_WORKPROBA_PROJET = "workproba.projet"
PLUGIN_WORKPROBA_PERSONAS = "workproba.personas"
PLUGIN_WORKPROBA_BROWSER = "workproba.browser"
PLUGIN_WORKPROBA_CLOUD = "workproba.cloud"


@dataclass(frozen=True)
class PluginManifest:
    id: str
    version: str
    permissions: frozenset[str]
    tools: frozenset[str]
    hooks: frozenset[str]
    default_enabled: bool = False


_BUILTIN_MANIFESTS: dict[str, PluginManifest] = {
    PLUGIN_WORKPROBA_PROJET: PluginManifest(
        id=PLUGIN_WORKPROBA_PROJET,
        version=projet_manifest.VERSION,
        permissions=frozenset(projet_manifest.PERMISSIONS),
        tools=frozenset(projet_manifest.TOOLS),
        hooks=frozenset(projet_manifest.HOOKS),
        default_enabled=projet_manifest.DEFAULT_ENABLED,
    ),
    PLUGIN_WORKPROBA_PERSONAS: PluginManifest(
        id=PLUGIN_WORKPROBA_PERSONAS,
        version=personas_manifest.VERSION,
        permissions=frozenset(personas_manifest.PERMISSIONS),
        tools=frozenset(personas_manifest.TOOLS),
        hooks=frozenset(personas_manifest.HOOKS),
        default_enabled=personas_manifest.DEFAULT_ENABLED,
    ),
    PLUGIN_WORKPROBA_BROWSER: PluginManifest(
        id=PLUGIN_WORKPROBA_BROWSER,
        version=browser_manifest.VERSION,
        permissions=frozenset(browser_manifest.PERMISSIONS),
        tools=frozenset(browser_manifest.TOOLS),
        hooks=frozenset(browser_manifest.HOOKS),
        default_enabled=browser_manifest.DEFAULT_ENABLED,
    ),
    PLUGIN_WORKPROBA_CLOUD: PluginManifest(
        id=PLUGIN_WORKPROBA_CLOUD,
        version=cloud_manifest.VERSION,
        permissions=frozenset(cloud_manifest.PERMISSIONS),
        tools=frozenset(cloud_manifest.TOOLS),
        hooks=frozenset(cloud_manifest.HOOKS),
        default_enabled=cloud_manifest.DEFAULT_ENABLED,
    ),
}


def get_builtin_plugins() -> dict[str, PluginManifest]:
    return dict(_BUILTIN_MANIFESTS)


def is_plugin_active(plugin_id: str, active_plugins: list[str] | None) -> bool:
    if not active_plugins:
        return False
    return plugin_id in active_plugins


def _plugins_root(plugin_data_dir: Path) -> Path:
    """Racine `.../plugins` quelle que soit la dir plugin passée au tour agent."""
    resolved = plugin_data_dir.expanduser().resolve()
    if resolved.name.startswith("workproba."):
        return resolved.parent
    return resolved


def _plugin_data_dir_for(
    plugin_id: str,
    plugin_data_dir: Path | None,
) -> Path | None:
    if plugin_data_dir is None:
        return None
    return _plugins_root(plugin_data_dir) / plugin_id


def resolve_plugin_data_dir(
    plugin_id: str,
    plugin_data_dir: Path | None,
) -> Path | None:
    """Résout la dir données d'un plugin depuis n'importe quelle dir plugin du tour."""
    return _plugin_data_dir_for(plugin_id, plugin_data_dir)


def build_plugin_contexts(
    *,
    active_plugins: list[str] | None,
    plugin_data_dir: Path | None,
    locale: str,
    provider_set: Any,
    permissions_by_plugin: dict[str, frozenset[str]] | None = None,
    workspace_data_dir: Path | None = None,
    project_root: Path | None = None,
) -> dict[str, PluginContext]:
    if not active_plugins:
        return {}

    contexts: dict[str, PluginContext] = {}
    for plugin_id in active_plugins:
        if plugin_id not in _BUILTIN_MANIFESTS:
            continue
        manifest = _BUILTIN_MANIFESTS[plugin_id]
        data_dir = _plugin_data_dir_for(plugin_id, plugin_data_dir)
        if data_dir is None:
            continue
        perms = permissions_by_plugin.get(plugin_id) if permissions_by_plugin else None
        if perms is None:
            perms = manifest.permissions
        contexts[plugin_id] = PluginContext(
            plugin_id=plugin_id,
            plugin_data_dir=data_dir,
            locale=locale,
            provider_set=provider_set,
            permissions=perms,
            workspace_data_dir=workspace_data_dir,
            project_root=project_root,
        )
    return contexts


def register_plugin_hooks(active_plugins: list[str] | None) -> None:
    """Enregistre les handlers des plugins actifs (idempotent par tour)."""
    hook_registry.unsubscribe_plugin(PLUGIN_WORKPROBA_PROJET)
    if is_plugin_active(PLUGIN_WORKPROBA_PROJET, active_plugins):
        for event, handler in projet_hooks.HANDLERS.items():
            hook_registry.subscribe(PLUGIN_WORKPROBA_PROJET, event, handler)


def register_plugin_tools(
    agent: Agent[Any, str],
    *,
    active_plugins: list[str] | None,
    plugin_data_dir: Path | None = None,
    ui_mode: Literal["guided", "advanced", "locked"] = "guided",
) -> None:
    """Ajoute les outils agent des plugins actifs."""
    if is_plugin_active(PLUGIN_WORKPROBA_PROJET, active_plugins):
        from app.plugins.workproba_projet.plugin import register_projet_tools

        register_projet_tools(agent)
    if is_plugin_active(PLUGIN_WORKPROBA_PERSONAS, active_plugins):
        from app.plugins.workproba_personas.plugin import register_personas_tools

        register_personas_tools(agent)
    if is_plugin_active(PLUGIN_WORKPROBA_BROWSER, active_plugins):
        from app.plugins.workproba_browser.plugin import register_browser_tools

        register_browser_tools(agent)
    if is_plugin_active(PLUGIN_WORKPROBA_CLOUD, active_plugins):
        from app.plugins.workproba_cloud.plugin import register_cloud_tools

        register_cloud_tools(
            agent,
            plugin_data_dir=plugin_data_dir,
            ui_mode=ui_mode,
        )


__all__ = [
    "PLUGIN_WORKPROBA_PROJET",
    "PLUGIN_WORKPROBA_PERSONAS",
    "PLUGIN_WORKPROBA_BROWSER",
    "PLUGIN_WORKPROBA_CLOUD",
    "PluginManifest",
    "build_plugin_contexts",
    "get_builtin_plugins",
    "is_plugin_active",
    "register_plugin_hooks",
    "register_plugin_tools",
    "resolve_plugin_data_dir",
]
