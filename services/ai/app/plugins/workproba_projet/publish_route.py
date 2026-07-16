"""Routage publish projet : cloud SoT si enrollé, local sinon."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD
from app.plugins.workproba_cloud import storage as cloud_storage
from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient
from app.plugins.workproba_cloud.sync_service import (
    is_cloud_enrolled,
    publish_shared_artefact_to_cloud,
)
from app.plugins.workproba_projet import storage


def cloud_dir_for(plugin_data_dir: Path) -> Path:
    return plugin_data_dir.expanduser().resolve().parent / PLUGIN_WORKPROBA_CLOUD


def cloud_publish_enabled(cloud_dir: Path) -> bool:
    base_url = cloud_storage.get_control_plane_base_url(cloud_dir)
    return is_cloud_enrolled(cloud_dir) and bool(base_url)


def prepare_publish_bytes(
    *,
    workspace_root: Path | None,
    source_path: str | None,
    content: str | None,
    name: str,
) -> tuple[str, bytes]:
    has_source = bool(source_path and source_path.strip())
    has_content = content is not None
    if has_content:
        encoded = content.encode("utf-8")
        if len(encoded) > storage.MAX_PUBLISH_CONTENT_BYTES:
            raise ValueError("content_too_large")
        filename = storage._sanitize_artefact_name(name, markdown=True)
        return filename, encoded
    if not has_source:
        raise ValueError("missing_publish_source")
    filename = storage._sanitize_artefact_name(name)
    if workspace_root is None:
        raise ValueError("missing_workspace_root")
    source = storage.resolve_source_in_workspace(workspace_root, source_path or "")
    payload = source.read_bytes()
    if len(payload) > storage.MAX_PUBLISH_CONTENT_BYTES:
        raise ValueError("content_too_large")
    return filename, payload


async def publish_artefact_routed(
    *,
    plugin_data_dir: Path,
    workspace_root: Path | None = None,
    source_path: str | None = None,
    content: str | None = None,
    project_id: str,
    name: str,
    work_id: str | None = None,
) -> dict[str, Any]:
    project = storage.find_project(plugin_data_dir, project_id)
    if project is None:
        raise ValueError("project_not_found")

    cloud_dir = cloud_dir_for(plugin_data_dir)
    if cloud_publish_enabled(cloud_dir):
        filename, payload = prepare_publish_bytes(
            workspace_root=workspace_root,
            source_path=source_path,
            content=content,
            name=name,
        )
        base_url = cloud_storage.get_control_plane_base_url(cloud_dir)
        if not base_url:
            raise ValueError("cloud_not_configured")
        client = CloudControlPlaneClient(base_url=base_url, plugin_data_dir=cloud_dir)
        artefact = await publish_shared_artefact_to_cloud(
            cloud_dir=cloud_dir,
            client=client,
            project_id=project_id,
            filename=filename,
            content=payload,
        )
        project_name = str(project.get("name") or project_id)
        from app.agent.work_events import audit_details_with_work_id
        from app.audit import log_event, resolve_app_data_dir

        log_event(
            resolve_app_data_dir(plugin_data_dir.parent),
            "publish_artifact",
            "user",
            audit_details_with_work_id(
                {"project_id": project_id, "name": filename, "source": "cloud"},
                work_id,
            ),
        )
        return {**artefact, "project_name": project_name}

    return storage.publish_artifact(
        plugin_data_dir=plugin_data_dir,
        workspace_root=workspace_root,
        source_path=source_path,
        content=content,
        project_id=project_id,
        name=name,
        work_id=work_id,
    )
