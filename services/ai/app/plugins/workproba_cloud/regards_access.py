"""Accès cloud au port ManagedRegardsPort (sans lecture directe du namespace personas)."""

from __future__ import annotations

from pathlib import Path

from app.plugins.ports.managed_regards import FilesystemManagedRegardsPort, open_managed_regards_port
from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD, get_builtin_plugins


def open_managed_regards_port_for_cloud(plugins_root: Path) -> FilesystemManagedRegardsPort:
    manifest = get_builtin_plugins()[PLUGIN_WORKPROBA_CLOUD]
    return open_managed_regards_port(
        caller_plugin_id=PLUGIN_WORKPROBA_CLOUD,
        caller_permissions=manifest.permissions,
        plugins_root=plugins_root,
    )
