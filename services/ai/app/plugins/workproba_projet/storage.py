"""Stockage namespace plugin projet (projects.json + artefacts)."""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.audit import log_event, resolve_app_data_dir


PROJECTS_FILE = "projects.json"
MAX_PUBLISH_CONTENT_BYTES = 5 * 1024 * 1024


def _projects_path(plugin_data_dir: Path) -> Path:
    return plugin_data_dir / PROJECTS_FILE


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def load_projects(plugin_data_dir: Path) -> list[dict[str, Any]]:
    path = _projects_path(plugin_data_dir)
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        return []
    projects = raw.get("projects")
    return list(projects) if isinstance(projects, list) else []


def save_projects(plugin_data_dir: Path, projects: list[dict[str, Any]]) -> None:
    plugin_data_dir.mkdir(parents=True, exist_ok=True)
    path = _projects_path(plugin_data_dir)
    with path.open("w", encoding="utf-8") as handle:
        json.dump({"projects": projects}, handle, ensure_ascii=False, indent=2)


def find_project(plugin_data_dir: Path, project_id: str) -> dict[str, Any] | None:
    for project in load_projects(plugin_data_dir):
        if project.get("id") == project_id:
            return project
    return None


def create_project(plugin_data_dir: Path, name: str) -> dict[str, Any]:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("invalid_project_name")
    project = {
        "id": f"proj_{uuid.uuid4().hex[:12]}",
        "name": cleaned,
        "created_at": _now_iso(),
    }
    projects = load_projects(plugin_data_dir)
    projects.append(project)
    save_projects(plugin_data_dir, projects)
    artefacts_dir(plugin_data_dir, project["id"]).mkdir(parents=True, exist_ok=True)
    return project


def artefacts_dir(plugin_data_dir: Path, project_id: str) -> Path:
    return plugin_data_dir / "artefacts" / project_id


def list_artefacts(plugin_data_dir: Path, project_id: str) -> list[dict[str, Any]]:
    if find_project(plugin_data_dir, project_id) is None:
        raise ValueError("project_not_found")
    directory = artefacts_dir(plugin_data_dir, project_id)
    if not directory.is_dir():
        return []
    artefacts: list[dict[str, Any]] = []
    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        stat = path.stat()
        published_at = datetime.fromtimestamp(stat.st_mtime, UTC).isoformat()
        artefacts.append(
            {
                "id": path.name,
                "name": path.name,
                "project_id": project_id,
                "path": path.as_posix(),
                "size_bytes": stat.st_size,
                "published_at": published_at,
                "created_at": published_at,
            }
        )
    return artefacts


def normalize_relative_path(file_path: str) -> str:
    normalized = file_path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lstrip("/")


def resolve_source_in_workspace(
    workspace_root: Path,
    source_path: str,
) -> Path:
    """Résout source_path dans workspace_root avec anti path traversal."""
    normalized = normalize_relative_path(source_path)
    if not normalized or normalized.startswith(".."):
        raise ValueError("path_outside_workspace")
    base = workspace_root.resolve()
    target = (base / normalized).resolve()
    if not target.is_relative_to(base):
        raise ValueError("path_outside_workspace")
    if not target.is_file():
        raise FileNotFoundError(normalized)
    return target


def _sanitize_artefact_name(name: str, *, markdown: bool = False) -> str:
    artefact_name = Path(name).name
    if not artefact_name or artefact_name in {".", ".."}:
        raise ValueError("invalid_artefact_name")
    if markdown:
        stem = Path(artefact_name).stem
        if not stem:
            raise ValueError("invalid_artefact_name")
        artefact_name = f"{stem}.md"
    return artefact_name


def _resolve_artefact_dest(dest_dir: Path, artefact_name: str) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = (dest_dir / artefact_name).resolve()
    if not dest.is_relative_to(dest_dir.resolve()):
        raise ValueError("path_outside_workspace")
    return dest


def publish_artifact(
    *,
    plugin_data_dir: Path,
    workspace_root: Path | None = None,
    source_path: str | None = None,
    content: str | None = None,
    project_id: str,
    name: str,
    work_id: str | None = None,
) -> dict[str, Any]:
    project = find_project(plugin_data_dir, project_id)
    if project is None:
        raise ValueError("project_not_found")

    has_source = bool(source_path and source_path.strip())
    has_content = content is not None
    if has_source and has_content:
        raise ValueError("ambiguous_publish_source")
    if not has_source and not has_content:
        raise ValueError("missing_publish_source")

    dest_dir = artefacts_dir(plugin_data_dir, project_id)
    published_at = _now_iso()
    audit_details: dict[str, Any] = {"project_id": project_id}

    if has_content:
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_PUBLISH_CONTENT_BYTES:
            raise ValueError("content_too_large")
        artefact_name = _sanitize_artefact_name(name, markdown=True)
        dest = _resolve_artefact_dest(dest_dir, artefact_name)
        dest.write_text(content, encoding="utf-8")
        audit_details["name"] = artefact_name
        audit_details["source"] = "content"
        result_source_path: str | None = None
    else:
        if workspace_root is None:
            raise ValueError("missing_workspace_root")
        artefact_name = _sanitize_artefact_name(name)
        source = resolve_source_in_workspace(workspace_root, source_path or "")
        dest = _resolve_artefact_dest(dest_dir, artefact_name)
        shutil.copy2(source, dest)
        audit_details["name"] = artefact_name
        result_source_path = normalize_relative_path(source_path or "")

    stat = dest.stat()
    from app.agent.work_events import audit_details_with_work_id

    log_event(
        resolve_app_data_dir(plugin_data_dir.parent),
        "publish_artifact",
        "user",
        audit_details_with_work_id(audit_details, work_id),
    )
    result: dict[str, Any] = {
        "id": artefact_name,
        "name": artefact_name,
        "path": dest.as_posix(),
        "project_id": project_id,
        "project_name": project.get("name", project_id),
        "size_bytes": stat.st_size,
        "published_at": published_at,
        "created_at": published_at,
    }
    if result_source_path is not None:
        result["source_path"] = result_source_path
    return result
