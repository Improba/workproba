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
    import os
    import tempfile

    plugin_data_dir.mkdir(parents=True, exist_ok=True)
    existing = load_config(plugin_data_dir)
    existing.update(config)
    target = _config_path(plugin_data_dir)
    fd, tmp_name = tempfile.mkstemp(
        prefix=".config.",
        suffix=".json.tmp",
        dir=str(plugin_data_dir),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(existing, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp_name, target)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
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


def get_device_id(plugin_data_dir: Path) -> str | None:
    tokens = load_config(plugin_data_dir).get("tokens")
    if not isinstance(tokens, dict):
        return None
    raw = tokens.get("device_id")
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


def get_disabled_managed_connectors(plugin_data_dir: Path) -> set[str]:
    """Connecteurs org désactivés localement (toujours listés si allowlistés)."""
    raw = load_config(plugin_data_dir).get("disabled_managed_connectors")
    if not isinstance(raw, list):
        return set()
    return {str(item).strip() for item in raw if isinstance(item, str) and str(item).strip()}


def is_managed_connector_enabled(plugin_data_dir: Path, connector_id: str) -> bool:
    cid = (connector_id or "").strip()
    if not cid:
        return False
    return cid not in get_disabled_managed_connectors(plugin_data_dir)


def _normalize_managed_tool_entry(entry: Any) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    name = entry.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    action = entry.get("action")
    if not isinstance(action, str) or not action.strip():
        return None
    normalized: dict[str, Any] = {
        "name": name.strip(),
        "action": action.strip(),
    }
    description = entry.get("description")
    if isinstance(description, str) and description.strip():
        normalized["description"] = description.strip()
    effect = entry.get("effect")
    if isinstance(effect, str) and effect.strip():
        normalized["effect"] = effect.strip()
    visibility = entry.get("visibility")
    if isinstance(visibility, str) and visibility.strip():
        normalized["visibility"] = visibility.strip()
    input_schema = entry.get("input_schema")
    if isinstance(input_schema, dict):
        normalized["input_schema"] = input_schema
    return normalized


def get_known_managed_connectors(plugin_data_dir: Path) -> list[dict[str, Any]]:
    """Derniers connecteurs org connus (cache disque pour le prompt agent)."""
    raw = load_config(plugin_data_dir).get("known_managed_connectors")
    if not isinstance(raw, list):
        return []
    connectors: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        cid = entry.get("id")
        if not isinstance(cid, str) or not cid.strip():
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            name = cid.strip()
        connector: dict[str, Any] = {"id": cid.strip(), "name": name.strip()}
        tools_raw = entry.get("tools")
        if isinstance(tools_raw, list):
            tools: list[dict[str, Any]] = []
            for tool_entry in tools_raw:
                normalized_tool = _normalize_managed_tool_entry(tool_entry)
                if normalized_tool is not None:
                    tools.append(normalized_tool)
            if tools:
                connector["tools"] = tools
        connectors.append(connector)
    return connectors


def save_known_managed_connectors(
    plugin_data_dir: Path,
    connectors: list[dict[str, Any]],
) -> None:
    """Met à jour le cache disque id/name/tools des connecteurs managés."""
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in connectors:
        if not isinstance(entry, dict):
            continue
        cid = entry.get("id")
        if not isinstance(cid, str) or not cid.strip():
            continue
        cid = cid.strip()
        if cid in seen:
            continue
        seen.add(cid)
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            name = cid
        connector: dict[str, Any] = {"id": cid, "name": name.strip()}
        tools_raw = entry.get("tools")
        if isinstance(tools_raw, list):
            tools: list[dict[str, Any]] = []
            for tool_entry in tools_raw:
                normalized_tool = _normalize_managed_tool_entry(tool_entry)
                if normalized_tool is not None:
                    tools.append(normalized_tool)
            if tools:
                connector["tools"] = tools
        normalized.append(connector)
    save_config(plugin_data_dir, {"known_managed_connectors": normalized})


def set_managed_connector_enabled(
    plugin_data_dir: Path,
    connector_id: str,
    *,
    enabled: bool,
) -> bool:
    """Active ou désactive localement un connecteur managé. Retourne l'état enabled."""
    cid = (connector_id or "").strip()
    if not cid:
        raise ValueError("connector_id_required")
    disabled = get_disabled_managed_connectors(plugin_data_dir)
    if enabled:
        disabled.discard(cid)
    else:
        disabled.add(cid)
    save_config(
        plugin_data_dir,
        {"disabled_managed_connectors": sorted(disabled)},
    )
    return enabled


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
        "device_id": get_device_id(plugin_data_dir),
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
