"""Port typé ProjectSyncPort — accès audité au namespace projet pour la sync."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.audit import log_event, resolve_app_data_dir
from app.plugins.registry import PLUGIN_WORKPROBA_PROJET
from app.plugins.workproba_projet import storage

PROJECT_SYNC_PERMISSION = "project:sync"


def parse_blob_id(blob_id: str) -> tuple[str, str]:
    """Identifiant contrat : `{project_id}/{artefact_name}`."""
    parts = blob_id.split("/", 1)
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        raise ValueError("invalid_blob_id")
    return parts[0].strip(), Path(parts[1].strip()).name


_SYNC_AUDIT_LOG: list[dict[str, Any]] = []


def sync_audit_log() -> list[dict[str, Any]]:
    """Journal des appels ProjectSyncPort (tests / audit)."""
    return list(_SYNC_AUDIT_LOG)


def clear_sync_audit_log() -> None:
    _SYNC_AUDIT_LOG.clear()


class ProjectSyncPort:
    """Surface contrôlée pour lire le namespace projet (sync cloud, V2)."""

    def __init__(
        self,
        *,
        projet_data_dir: Path,
        caller_plugin_id: str,
        app_data_dir: Path,
    ) -> None:
        self._projet_data_dir = projet_data_dir
        self._caller_plugin_id = caller_plugin_id
        self._app_data_dir = app_data_dir

    def _audit(self, op: str, detail: dict[str, Any]) -> None:
        entry = {
            "caller": self._caller_plugin_id,
            "op": op,
            **detail,
        }
        _SYNC_AUDIT_LOG.append(entry)
        log_event(
            self._app_data_dir,
            "plugin.project_sync",
            f"plugin:{self._caller_plugin_id}",
            {"op": op, **detail},
        )

    def list_projects(self) -> list[dict[str, Any]]:
        self._audit("list_projects", {})
        return storage.load_projects(self._projet_data_dir)

    def list_artefacts(self, project_id: str) -> list[dict[str, Any]]:
        self._audit("list_artefacts", {"project_id": project_id})
        return storage.list_artefacts(self._projet_data_dir, project_id)

    def _read_artefact_bytes(self, project_id: str, artefact_id: str) -> bytes:
        if storage.find_project(self._projet_data_dir, project_id) is None:
            raise ValueError("project_not_found")
        safe_name = Path(artefact_id).name
        path = storage.artefacts_dir(self._projet_data_dir, project_id) / safe_name
        if not path.is_file():
            raise ValueError("artefact_not_found")
        return path.read_bytes()

    def read_blob(self, blob_id: str) -> bytes:
        project_id, artefact_id = parse_blob_id(blob_id)
        self._audit(
            "read_blob",
            {"blob_id": blob_id, "project_id": project_id, "artefact_id": artefact_id},
        )
        return self._read_artefact_bytes(project_id, artefact_id)

    def read_artefact(self, project_id: str, artefact_id: str) -> bytes:
        self._audit(
            "read_artefact",
            {"project_id": project_id, "artefact_id": artefact_id},
        )
        return self._read_artefact_bytes(project_id, artefact_id)

    def list_changes(self, cursor: str | None = None) -> dict[str, Any]:
        self._audit("list_changes", {"cursor": cursor})
        changes: list[dict[str, Any]] = []
        for project in storage.load_projects(self._projet_data_dir):
            project_id = str(project.get("id", ""))
            if not project_id:
                continue
            try:
                artefacts = storage.list_artefacts(self._projet_data_dir, project_id)
            except ValueError:
                continue
            for artefact in artefacts:
                artefact_id = str(artefact.get("id", ""))
                if not artefact_id:
                    continue
                changes.append(
                    {
                        "project_id": project_id,
                        "artefact_id": artefact_id,
                        "blob_id": f"{project_id}/{artefact_id}",
                        "published_at": artefact.get("published_at"),
                    }
                )
        return {"changes": changes, "cursor": None}

    def apply_remote_change(self, change: dict[str, Any]) -> dict[str, Any]:
        self._audit("apply_remote_change", {"change_keys": sorted(change.keys())})
        project_id = change.get("project_id")
        artefact_id = change.get("artefact_id")
        content = change.get("content")
        version = change.get("version")
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("invalid_remote_change")
        if not isinstance(artefact_id, str) or not artefact_id.strip():
            raise ValueError("invalid_remote_change")
        if content is None:
            raise ValueError("invalid_remote_change")
        if isinstance(content, str):
            payload = content.encode("utf-8")
        elif isinstance(content, bytes):
            payload = content
        else:
            raise ValueError("invalid_remote_change")
        version_value = str(version) if version is not None else None
        return self.write_artefact(
            project_id.strip(),
            artefact_id.strip(),
            payload,
            version=version_value,
        )

    def write_artefact(
        self,
        project_id: str,
        artefact_id: str,
        content: bytes,
        version: str | None = None,
    ) -> dict[str, Any]:
        safe_name = Path(artefact_id).name
        self._audit(
            "write_artefact",
            {
                "project_id": project_id,
                "artefact_id": safe_name,
                "version": version,
                "size_bytes": len(content),
            },
        )
        return storage.write_published_artefact(
            self._projet_data_dir,
            project_id,
            safe_name,
            content,
            version=version,
        )


def open_project_sync_port(
    *,
    caller_plugin_id: str,
    caller_permissions: frozenset[str],
    plugins_root: Path,
) -> ProjectSyncPort:
    if PROJECT_SYNC_PERMISSION not in caller_permissions:
        raise PermissionError(f"Missing permission: {PROJECT_SYNC_PERMISSION}")

    projet_data_dir = plugins_root / PLUGIN_WORKPROBA_PROJET
    app_data_dir = resolve_app_data_dir(plugins_root)
    return ProjectSyncPort(
        projet_data_dir=projet_data_dir,
        caller_plugin_id=caller_plugin_id,
        app_data_dir=app_data_dir,
    )
