"""Stockage et sync locale du plugin cloud (mount point OS)."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.plugins.workproba_projet import storage as projet_storage

CONFIG_FILE = "config.json"


def _config_path(plugin_data_dir: Path) -> Path:
    return plugin_data_dir / CONFIG_FILE


def load_config(plugin_data_dir: Path) -> dict[str, Any]:
    path = _config_path(plugin_data_dir)
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return raw if isinstance(raw, dict) else {}


def save_config(plugin_data_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    plugin_data_dir.mkdir(parents=True, exist_ok=True)
    existing = load_config(plugin_data_dir)
    existing.update(config)
    with _config_path(plugin_data_dir).open("w", encoding="utf-8") as handle:
        json.dump(existing, handle, ensure_ascii=False, indent=2)
    return existing


def get_mount_path(plugin_data_dir: Path) -> str | None:
    raw = load_config(plugin_data_dir).get("mount_path")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def status(plugin_data_dir: Path, projet_plugin_dir: Path) -> dict[str, Any]:
    mount_path = get_mount_path(plugin_data_dir)
    config = load_config(plugin_data_dir)
    synced_count = 0
    if mount_path:
        mount = Path(mount_path).expanduser()
        if mount.is_dir():
            synced_count = sum(1 for _ in mount.rglob("*") if _.is_file())
    return {
        "configured": mount_path is not None,
        "mount_path": mount_path,
        "last_sync": config.get("last_sync"),
        "synced_count": synced_count,
    }


def sync_project(
    *,
    plugin_data_dir: Path,
    projet_plugin_dir: Path,
    project_id: str,
    mount_path: str | None = None,
) -> dict[str, Any]:
    """Copie les artefacts publiés vers mount_path/projects/{project_id}/."""
    if projet_storage.find_project(projet_plugin_dir, project_id) is None:
        raise ValueError("project_not_found")

    effective_mount = mount_path or get_mount_path(plugin_data_dir)
    if not effective_mount:
        raise ValueError("cloud_not_configured")

    mount = Path(effective_mount).expanduser().resolve()
    mount.mkdir(parents=True, exist_ok=True)
    dest_root = mount / "projects" / project_id
    dest_root.mkdir(parents=True, exist_ok=True)

    source_dir = projet_storage.artefacts_dir(projet_plugin_dir, project_id)
    synced: list[str] = []
    if source_dir.is_dir():
        for source in sorted(source_dir.iterdir()):
            if not source.is_file():
                continue
            dest = dest_root / source.name
            shutil.copy2(source, dest)
            synced.append(source.name)

    now = datetime.now(UTC).isoformat()
    save_config(plugin_data_dir, {"mount_path": str(mount), "last_sync": now})
    return {"synced": synced, "mount_path": str(mount), "last_sync": now}
