"""Snapshots de fichiers avant écriture agent (stockage canonique app_data)."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.audit import log_event, resolve_app_data_dir

logger = logging.getLogger(__name__)

VERSIONS_DIR = "versions"
MANIFEST_FILENAME = "manifest.json"
JsonDict = dict[str, Any]
DEFAULT_MAX_VERSIONS_PER_FILE = 50


def normalize_relative_path(file_path: str) -> str:
    normalized = file_path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lstrip("/")


def file_path_hash(relative_path: str) -> str:
    normalized = normalize_relative_path(relative_path)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def versions_dir_for_file(workspace_data_dir: Path, relative_path: str) -> Path:
    from app.memory_stores import workspace_storage_root

    root = workspace_storage_root(workspace_data_dir)
    return root / VERSIONS_DIR / file_path_hash(relative_path)


def load_manifest(manifest_path: Path) -> list[JsonDict]:
    if not manifest_path.is_file():
        return []
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Impossible de lire le manifeste %s : %s", manifest_path, exc)
        return []
    if isinstance(data, list):
        return [entry for entry in data if isinstance(entry, dict)]
    if isinstance(data, dict):
        entries = data.get("entries") or data.get("versions")
        if isinstance(entries, list):
            return [entry for entry in entries if isinstance(entry, dict)]
    return []


def save_manifest(manifest_path: Path, entries: list[JsonDict]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def rotate_versions(
    *,
    version_dir: Path,
    manifest_path: Path,
    max_versions: int = DEFAULT_MAX_VERSIONS_PER_FILE,
) -> None:
    """Rotation FIFO des snapshots (garde les `max_versions` plus récents)."""
    if max_versions <= 0:
        return
    entries = load_manifest(manifest_path)
    if len(entries) <= max_versions:
        return
    overflow = entries[: len(entries) - max_versions]
    kept = entries[len(entries) - max_versions :]
    for entry in overflow:
        version_id = entry.get("version_id")
        if not isinstance(version_id, str) or not version_id:
            continue
        snapshot_path = version_dir / f"{version_id}.bin"
        try:
            snapshot_path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Impossible de supprimer %s : %s", snapshot_path, exc)
    save_manifest(manifest_path, kept)


def snapshot_before_overwrite(
    *,
    workspace_data_dir: Path | None,
    project_root: Path,
    relative_path: str,
    label: str | None = None,
    max_versions: int = DEFAULT_MAX_VERSIONS_PER_FILE,
) -> JsonDict | None:
    """Copie le fichier existant avant écrasement dans workspace_data_dir/versions/."""
    if workspace_data_dir is None:
        return None

    root = project_root.expanduser().resolve()
    ws_dir = workspace_data_dir.expanduser().resolve()
    normalized = normalize_relative_path(relative_path)
    target = (root / normalized).resolve()
    if not target.is_file():
        return None
    if not target.is_relative_to(root):
        logger.warning("Chemin hors projet ignoré pour snapshot : %s", relative_path)
        return None

    version_dir = versions_dir_for_file(ws_dir, normalized)
    try:
        version_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("Impossible de créer %s : %s", version_dir, exc)
        return None

    now = datetime.now(timezone.utc)
    version_id = f"v_{now.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
    snapshot_path = version_dir / f"{version_id}.bin"
    try:
        shutil.copy2(target, snapshot_path)
    except OSError as exc:
        logger.warning("Impossible de copier %s vers %s : %s", target, snapshot_path, exc)
        return None

    size = snapshot_path.stat().st_size
    entry: JsonDict = {
        "version_id": version_id,
        "file_path": normalized,
        "created_at": now.isoformat(),
        "size": size,
        "label": label or "",
    }
    manifest_path = version_dir / MANIFEST_FILENAME
    try:
        entries = load_manifest(manifest_path)
        entries.append(entry)
        save_manifest(manifest_path, entries)
        rotate_versions(
            version_dir=version_dir,
            manifest_path=manifest_path,
            max_versions=max_versions,
        )
    except OSError as exc:
        logger.warning("Impossible de mettre à jour %s : %s", manifest_path, exc)
    return entry


def list_versions(
    *,
    workspace_data_dir: Path,
    file_path: str,
) -> list[JsonDict]:
    ws_dir = workspace_data_dir.expanduser().resolve()
    normalized = normalize_relative_path(file_path)
    manifest_path = versions_dir_for_file(ws_dir, normalized) / MANIFEST_FILENAME
    entries = [
        entry
        for entry in load_manifest(manifest_path)
        if entry.get("file_path", normalized) == normalized or not entry.get("file_path")
    ]
    return list(reversed(entries))


def restore_version(
    *,
    workspace_data_dir: Path,
    project_root: Path,
    file_path: str,
    version_id: str,
    label: str | None = None,
) -> JsonDict:
    ws_dir = workspace_data_dir.expanduser().resolve()
    root = project_root.expanduser().resolve()
    normalized = normalize_relative_path(file_path)
    version_dir = versions_dir_for_file(ws_dir, normalized)
    snapshot_path = version_dir / f"{version_id}.bin"
    if not snapshot_path.is_file():
        raise FileNotFoundError(f"Version introuvable : {version_id}")

    manifest_path = version_dir / MANIFEST_FILENAME
    entry = next(
        (item for item in load_manifest(manifest_path) if item.get("version_id") == version_id),
        None,
    )
    if entry is None:
        raise ValueError(f"Version absente du manifeste : {version_id}")

    target = (root / normalized).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"Chemin cible invalide : {file_path}")

    snapshot_before_overwrite(
        workspace_data_dir=ws_dir,
        project_root=root,
        relative_path=normalized,
        label=label,
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(snapshot_path, target)
    log_event(
        resolve_app_data_dir(ws_dir),
        "version.restore",
        "user",
        {"file_path": normalized, "version_id": version_id},
    )
    return {
        "ok": True,
        "restored_path": normalized,
        "version_id": version_id,
        "file_path": normalized,
    }
