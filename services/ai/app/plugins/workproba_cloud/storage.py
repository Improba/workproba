"""Stockage et sync locale du plugin cloud (mount point OS)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.plugins.workproba_projet.sync_port import ProjectSyncPort

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


def get_control_plane_base_url(plugin_data_dir: Path) -> str | None:
    raw = load_config(plugin_data_dir).get("base_url")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def get_access_token(plugin_data_dir: Path) -> str | None:
    tokens = load_config(plugin_data_dir).get("tokens")
    if not isinstance(tokens, dict):
        return None
    raw = tokens.get("access_token")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def is_enrolled(plugin_data_dir: Path) -> bool:
    return (
        get_control_plane_base_url(plugin_data_dir) is not None
        and get_access_token(plugin_data_dir) is not None
    )


def get_org_id(plugin_data_dir: Path) -> str | None:
    tokens = load_config(plugin_data_dir).get("tokens")
    if not isinstance(tokens, dict):
        return None
    raw = tokens.get("org_id")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def get_org_label(plugin_data_dir: Path) -> str | None:
    tokens = load_config(plugin_data_dir).get("tokens")
    if not isinstance(tokens, dict):
        return None
    for key in ("org_label", "org_name", "profile", "org_id"):
        raw = tokens.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def clear_enrollment(plugin_data_dir: Path) -> None:
    """Supprime jetons et identifiants cloud (déconnexion locale)."""
    config = load_config(plugin_data_dir)
    config.pop("tokens", None)
    plugin_data_dir.mkdir(parents=True, exist_ok=True)
    with _config_path(plugin_data_dir).open("w", encoding="utf-8") as handle:
        json.dump(config, handle, ensure_ascii=False, indent=2)


def status(plugin_data_dir: Path) -> dict[str, Any]:
    mount_path = get_mount_path(plugin_data_dir)
    config = load_config(plugin_data_dir)
    base_url = get_control_plane_base_url(plugin_data_dir)
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
        "base_url": base_url,
        "enrolled": is_enrolled(plugin_data_dir),
        "has_token": get_access_token(plugin_data_dir) is not None,
        "org_id": get_org_id(plugin_data_dir),
        "org_label": get_org_label(plugin_data_dir),
    }


def sync_project(
    *,
    plugin_data_dir: Path,
    sync_port: ProjectSyncPort,
    project_id: str,
    mount_path: str | None = None,
) -> dict[str, Any]:
    """Copie les artefacts publiés vers mount_path/projects/{project_id}/ via ProjectSyncPort."""
    try:
        artefacts = sync_port.list_artefacts(project_id)
    except ValueError as exc:
        if str(exc) == "project_not_found":
            raise ValueError("project_not_found") from exc
        raise

    effective_mount = mount_path or get_mount_path(plugin_data_dir)
    if not effective_mount:
        raise ValueError("cloud_not_configured")

    mount = Path(effective_mount).expanduser().resolve()
    mount.mkdir(parents=True, exist_ok=True)
    dest_root = mount / "projects" / project_id
    dest_root.mkdir(parents=True, exist_ok=True)

    synced: list[str] = []
    for artefact in artefacts:
        artefact_id = str(artefact.get("id", ""))
        if not artefact_id:
            continue
        content = sync_port.read_blob(f"{project_id}/{artefact_id}")
        dest = dest_root / Path(artefact_id).name
        dest.write_bytes(content)
        synced.append(artefact_id)

    now = datetime.now(UTC).isoformat()
    save_config(plugin_data_dir, {"mount_path": str(mount), "last_sync": now})
    return {"synced": synced, "mount_path": str(mount), "last_sync": now}
