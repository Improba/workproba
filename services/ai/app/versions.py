"""Snapshots de fichiers projet avant écriture ou restauration."""

from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MANIFEST_FILENAME = "manifest.json"
JsonDict = dict[str, Any]


def versions_session_dir(project_root: Path, session_id: str) -> Path:
    return project_root / ".workproba" / "versions" / session_id


def snapshot_filename(original_name: str, timestamp: datetime) -> str:
    ts = timestamp.strftime("%Y%m%dT%H%M%S%f")
    safe_name = re.sub(r"[^\w.\-]+", "_", Path(original_name).name).strip("._")
    return f"{ts}__{safe_name or 'fichier'}"


def normalize_relative_path(file_path: str) -> str:
    normalized = file_path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


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
        entries = data.get("entries")
        if isinstance(entries, list):
            return [entry for entry in entries if isinstance(entry, dict)]
    return []


def save_manifest(manifest_path: Path, entries: list[JsonDict]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def snapshot_before_overwrite(
    *,
    project_root: Path,
    session_id: str,
    relative_path: str,
) -> JsonDict | None:
    """Copie le fichier existant avant écrasement. Échec doux si indisponible."""
    root = project_root.expanduser().resolve()
    normalized = normalize_relative_path(relative_path)
    target = (root / normalized).resolve()
    if not target.is_file():
        return None
    if not target.is_relative_to(root):
        logger.warning("Chemin hors projet ignoré pour snapshot : %s", relative_path)
        return None

    session_dir = versions_session_dir(root, session_id)
    try:
        session_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("Impossible de créer %s : %s", session_dir, exc)
        return None

    now = datetime.now(timezone.utc)
    snapshot_path = session_dir / snapshot_filename(target.name, now)
    try:
        shutil.copy2(target, snapshot_path)
    except OSError as exc:
        logger.warning("Impossible de copier %s vers %s : %s", target, snapshot_path, exc)
        return None

    entry: JsonDict = {
        "original_path": normalized,
        "snapshot_path": snapshot_path.relative_to(root).as_posix(),
        "timestamp": now.isoformat(),
        "session_id": session_id,
    }
    manifest_path = session_dir / MANIFEST_FILENAME
    try:
        entries = load_manifest(manifest_path)
        entries.append(entry)
        save_manifest(manifest_path, entries)
    except OSError as exc:
        logger.warning("Impossible de mettre à jour %s : %s", manifest_path, exc)
    return entry


def list_snapshots(
    *,
    project_root: Path,
    session_id: str,
    file_path: str,
) -> list[JsonDict]:
    root = project_root.expanduser().resolve()
    manifest_path = versions_session_dir(root, session_id) / MANIFEST_FILENAME
    normalized = normalize_relative_path(file_path)
    return [
        entry
        for entry in load_manifest(manifest_path)
        if entry.get("original_path") == normalized
    ]


def restore_snapshot(
    *,
    project_root: Path,
    session_id: str,
    snapshot_path: str,
) -> JsonDict:
    root = project_root.expanduser().resolve()
    normalized_snapshot = normalize_relative_path(snapshot_path)
    snap = (root / normalized_snapshot).resolve()
    if not snap.is_file() or not snap.is_relative_to(root):
        raise FileNotFoundError(f"Snapshot introuvable : {snapshot_path}")

    manifest_path = versions_session_dir(root, session_id) / MANIFEST_FILENAME
    entry = next(
        (
            item
            for item in load_manifest(manifest_path)
            if item.get("snapshot_path") == normalized_snapshot
        ),
        None,
    )
    if entry is None:
        raise ValueError(f"Snapshot absent du manifeste : {snapshot_path}")

    original_path = str(entry["original_path"])
    target = (root / original_path).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"Chemin original invalide : {original_path}")

    snapshot_before_overwrite(
        project_root=root,
        session_id=session_id,
        relative_path=original_path,
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(snap, target)
    return {
        "restored_path": original_path,
        "snapshot_path": normalized_snapshot,
        "session_id": session_id,
    }
