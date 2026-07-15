"""Accès cloud au port de sync projet (sans résolution directe du namespace)."""

from __future__ import annotations

from pathlib import Path

from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD, get_builtin_plugins
from app.plugins.workproba_projet.sync_port import ProjectSyncPort, open_project_sync_port


def open_sync_port_for_cloud(plugins_root: Path) -> ProjectSyncPort:
    manifest = get_builtin_plugins()[PLUGIN_WORKPROBA_CLOUD]
    return open_project_sync_port(
        caller_plugin_id=PLUGIN_WORKPROBA_CLOUD,
        caller_permissions=manifest.permissions,
        plugins_root=plugins_root,
    )
