"""Journal d'audit local JSONL (app_data/audit/audit.jsonl)."""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

AUDIT_SUBDIR = "audit"
AUDIT_FILENAME = "audit.jsonl"
CONFIG_FILENAME = "config.json"
DEFAULT_RETENTION_DAYS = 90
DEFAULT_ENABLED = True


def resolve_app_data_dir(path: Path) -> Path:
    """Dérive app_data depuis un chemin workspace, plugin ou app_data direct."""
    resolved = path.expanduser().resolve()
    parts = resolved.parts
    for marker in ("spaces", "workspaces", "plugins", "presets"):
        if marker in parts:
            idx = parts.index(marker)
            return Path(*parts[:idx])
    if (resolved / "settings.json").is_file() or (resolved / AUDIT_SUBDIR).is_dir():
        return resolved
    if resolved.name == AUDIT_SUBDIR and resolved.parent.is_dir():
        return resolved.parent
    return resolved


def resolve_user_data_dir(app_data_dir: Path) -> Path:
    """Dossier de données globales utilisateur (mémoire partagée entre espaces)."""
    return resolve_app_data_dir(app_data_dir) / "user"


def audit_dir(app_data_dir: Path) -> Path:
    return resolve_app_data_dir(app_data_dir) / AUDIT_SUBDIR


def audit_file_path(app_data_dir: Path) -> Path:
    return audit_dir(app_data_dir) / AUDIT_FILENAME


def config_file_path(app_data_dir: Path) -> Path:
    return audit_dir(app_data_dir) / CONFIG_FILENAME


def _load_config_file(app_data_dir: Path) -> dict[str, Any]:
    path = config_file_path(app_data_dir)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Audit config illisible %s : %s", path, exc)
        return {}
    return raw if isinstance(raw, dict) else {}


def _save_config_file(app_data_dir: Path, data: dict[str, Any]) -> None:
    directory = audit_dir(app_data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    config_file_path(app_data_dir).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_audit_config(
    app_data_dir: Path,
    *,
    preset_retention_days: int | None = None,
    preset_enabled: bool | None = None,
) -> dict[str, Any]:
    """Config effective : preset > fichier local > défauts."""
    stored = _load_config_file(app_data_dir)
    retention = preset_retention_days
    if retention is None:
        raw_retention = stored.get("retention_days")
        retention = int(raw_retention) if isinstance(raw_retention, int) else DEFAULT_RETENTION_DAYS
    enabled = preset_enabled
    if enabled is None:
        raw_enabled = stored.get("enabled")
        enabled = bool(raw_enabled) if isinstance(raw_enabled, bool) else DEFAULT_ENABLED
    return {"retention_days": retention, "enabled": enabled}


def save_audit_config(
    app_data_dir: Path,
    *,
    retention_days: int | None = None,
    enabled: bool | None = None,
) -> dict[str, Any]:
    data = _load_config_file(app_data_dir)
    if retention_days is not None:
        data["retention_days"] = retention_days
    if enabled is not None:
        data["enabled"] = enabled
    _save_config_file(app_data_dir, data)
    return get_audit_config(app_data_dir)


def log_event(
    app_data_dir: Path,
    event: str,
    actor: str,
    details: dict[str, Any] | None = None,
    *,
    enabled: bool | None = None,
) -> None:
    """Append une ligne JSONL si l'audit est activé."""
    root = resolve_app_data_dir(app_data_dir)
    config = get_audit_config(root)
    if enabled is False or (enabled is None and not config["enabled"]):
        return

    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event,
        "actor": actor,
        "details": details or {},
    }
    directory = audit_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    path = audit_file_path(root)
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.warning("Impossible d'écrire l'audit %s : %s", path, exc)
        return

    rotate(root, int(config["retention_days"]))


def _parse_timestamp(value: str) -> datetime | None:
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def read_audit(
    app_data_dir: Path,
    *,
    from_ts: str | None = None,
    to_ts: str | None = None,
    event: str | None = None,
    limit: int = 100,
) -> tuple[list[dict[str, Any]], int]:
    """Lit le journal avec filtres optionnels."""
    root = resolve_app_data_dir(app_data_dir)
    path = audit_file_path(root)
    if not path.is_file():
        return [], 0

    from_dt = _parse_timestamp(from_ts) if from_ts else None
    to_dt = _parse_timestamp(to_ts) if to_ts else None
    matched: list[dict[str, Any]] = []

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        logger.warning("Impossible de lire l'audit %s : %s", path, exc)
        return [], 0

    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        if event and entry.get("event") != event:
            continue
        ts_raw = entry.get("timestamp")
        if isinstance(ts_raw, str):
            ts = _parse_timestamp(ts_raw)
            if ts is not None:
                if from_dt and ts < from_dt:
                    continue
                if to_dt and ts > to_dt:
                    continue
        matched.append(entry)

    total = len(matched)
    if limit > 0:
        matched = matched[-limit:]
    return matched, total


def rotate(app_data_dir: Path, retention_days: int) -> int:
    """Rotation FIFO par date : supprime les entrées plus vieilles que la rétention."""
    if retention_days <= 0:
        return 0
    root = resolve_app_data_dir(app_data_dir)
    path = audit_file_path(root)
    if not path.is_file():
        return 0

    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    kept: list[str] = []
    removed = 0

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0

    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            kept.append(line)
            continue
        ts_raw = entry.get("timestamp") if isinstance(entry, dict) else None
        if isinstance(ts_raw, str):
            ts = _parse_timestamp(ts_raw)
            if ts is not None and ts < cutoff:
                removed += 1
                continue
        kept.append(line)

    if removed:
        path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    return removed


def export_audit_csv(
    app_data_dir: Path,
    *,
    from_ts: str | None = None,
    to_ts: str | None = None,
    event: str | None = None,
    limit: int = 0,
) -> str:
    """Exporte le journal d'audit en CSV (colonnes timestamp, event, actor, details)."""
    entries, _ = read_audit(
        app_data_dir,
        from_ts=from_ts,
        to_ts=to_ts,
        event=event,
        limit=limit,
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["timestamp", "event", "actor", "details"])
    for entry in entries:
        details = entry.get("details")
        if details is None:
            details_json = ""
        elif isinstance(details, dict):
            details_json = json.dumps(details, ensure_ascii=False)
        else:
            details_json = json.dumps(details, ensure_ascii=False, default=str)
        writer.writerow(
            [
                str(entry.get("timestamp") or ""),
                str(entry.get("event") or ""),
                str(entry.get("actor") or ""),
                details_json,
            ]
        )
    return buffer.getvalue()
