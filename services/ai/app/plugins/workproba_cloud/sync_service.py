"""Service partagé push/pull cloud (mount optionnel, control plane)."""

from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
from typing import Any

from pydantic_ai.exceptions import ModelRetry

from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient
from app.plugins.workproba_cloud import storage as cloud_storage
from app.plugins.workproba_projet.sync_port import ProjectSyncPort


def is_mount_configured(cloud_dir: Path) -> bool:
    return cloud_storage.get_mount_path(cloud_dir) is not None


def is_cloud_enrolled(cloud_dir: Path) -> bool:
    base_url = cloud_storage.get_control_plane_base_url(cloud_dir)
    if not base_url:
        return False
    token = CloudControlPlaneClient(
        base_url=base_url,
        plugin_data_dir=cloud_dir,
    ).load_tokens().get("access_token")
    return isinstance(token, str) and bool(token.strip())


def _parse_version(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for segment in version.split("."):
        try:
            parts.append(int(segment))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _is_remote_newer(local_version: str | None, remote_version: str | None) -> bool:
    if not remote_version:
        return False
    if not local_version:
        return True
    return _parse_version(remote_version) > _parse_version(local_version)


def _artifact_checksum(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _bump_patch_version(version: str) -> str:
    parts = version.split(".")
    while len(parts) < 3:
        parts.append("0")
    try:
        parts[2] = str(int(parts[2]) + 1)
    except ValueError:
        parts[2] = "1"
    return ".".join(parts[:3])


def _skip_reason(artifact_id: str, reason: str) -> str:
    return f"{artifact_id}:{reason}"


async def push_single_artefact(
    *,
    client: CloudControlPlaneClient,
    project_id: str,
    artifact_id: str,
    version: str,
    filename: str,
    content: bytes,
) -> dict[str, Any]:
    """Pousse métadonnées et blob d'un artefact vers le control plane."""
    checksum = _artifact_checksum(content)
    size = len(content)

    pushed = await client.push_sync_artefact_metadata(
        project_id=project_id,
        artifact_id=artifact_id,
        version=version,
        filename=filename,
        checksum=checksum,
        size=size,
    )

    artefact_db_id = pushed.get("id")
    if not isinstance(artefact_db_id, int):
        raise ModelRetry(
            f"Control plane: missing artefact id after metadata push for {artifact_id}"
        )

    verify = await client.verify_blob(artefact_db_id=artefact_db_id)
    if (
        verify.get("blobExists") is True
        and verify.get("confirmedAt")
        and pushed.get("checksum") == checksum
        and int(pushed.get("size") or 0) == size
    ):
        return {
            "artifact_id": artifact_id,
            "metadata_pushed": True,
            "blob_uploaded": False,
            "skipped": True,
            "summary": pushed,
        }

    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    upload = await client.request_upload_url(
        artefact_db_id=artefact_db_id,
        content_type=mime,
    )
    upload_url = upload.get("url")
    if not isinstance(upload_url, str) or not upload_url.strip():
        raise ModelRetry(f"Control plane: missing upload url for artefact {artifact_id}")

    await client.put_presigned_blob(
        url=upload_url.strip(),
        content=content,
        content_type=mime,
    )
    confirmed = await client.confirm_upload(artefact_db_id=artefact_db_id)
    return {
        "artifact_id": artifact_id,
        "metadata_pushed": True,
        "blob_uploaded": True,
        "skipped": False,
        "summary": confirmed,
    }


async def _resolve_cloud_artefact_version(
    *,
    client: CloudControlPlaneClient,
    project_id: str,
    artifact_id: str,
) -> str:
    remote = await client.list_sync_artefacts(project_id=project_id)
    versions: list[str] = []
    for item in remote.get("items") or []:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("artifactId") or item.get("filename") or "")
        if item_id == artifact_id:
            versions.append(str(item.get("version") or "1.0.0"))
    if not versions:
        return "1.0.0"
    latest = max(versions, key=_parse_version)
    return _bump_patch_version(latest)


def _map_cloud_item_to_projet_shape(
    item: dict[str, Any],
    *,
    project_id: str,
) -> dict[str, Any] | None:
    artifact_id = str(item.get("artifactId") or item.get("filename") or "")
    if not artifact_id:
        return None
    confirmed_at = item.get("confirmedAt")
    created_at = item.get("createdAt")
    timestamp = str(confirmed_at or created_at or "")
    cloud_confirmed = bool(confirmed_at)
    return {
        "id": artifact_id,
        "name": str(item.get("filename") or artifact_id),
        "project_id": project_id,
        "created_at": timestamp,
        "published_at": timestamp,
        "version": item.get("version"),
        "size_bytes": item.get("size"),
        "cloud_confirmed": cloud_confirmed,
        "cloud_pending": not cloud_confirmed,
    }


async def list_cloud_artefacts_for_project(
    *,
    client: CloudControlPlaneClient,
    project_id: str,
    cloud_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Liste les artefacts cloud mappés en shape compatible ProjectPanel."""
    from app.plugins.workproba_cloud.cache_service import has_cached_artefact

    remote = await client.list_sync_artefacts(project_id=project_id)
    items: list[dict[str, Any]] = []
    for item in remote.get("items") or []:
        if not isinstance(item, dict):
            continue
        mapped = _map_cloud_item_to_projet_shape(item, project_id=project_id)
        if mapped is not None:
            if cloud_dir is not None:
                mapped["has_local_cache"] = has_cached_artefact(
                    cloud_dir,
                    project_id=project_id,
                    artefact_id=str(mapped["id"]),
                )
            items.append(mapped)
    return items


async def publish_shared_artefact_to_cloud(
    *,
    cloud_dir: Path,
    client: CloudControlPlaneClient,
    project_id: str,
    filename: str,
    content: bytes,
    version: str | None = None,
) -> dict[str, Any]:
    """Publie un artefact directement dans le cloud sans SoT locale sous artefacts/."""
    _ = cloud_dir
    artifact_id = filename
    resolved_version = version or await _resolve_cloud_artefact_version(
        client=client,
        project_id=project_id,
        artifact_id=artifact_id,
    )
    push_result = await push_single_artefact(
        client=client,
        project_id=project_id,
        artifact_id=artifact_id,
        version=resolved_version,
        filename=filename,
        content=content,
    )
    summary = push_result.get("summary") or {}
    confirmed_at = summary.get("confirmedAt")
    created_at = str(confirmed_at or summary.get("createdAt") or "")
    return {
        "id": artifact_id,
        "name": filename,
        "project_id": project_id,
        "version": resolved_version,
        "size_bytes": len(content),
        "created_at": created_at,
        "published_at": created_at,
        "cloud_confirmed": bool(confirmed_at) or push_result.get("blob_uploaded") is True,
        "cloud_pending": not bool(confirmed_at) and push_result.get("skipped") is not True,
        "metadata_pushed": push_result.get("metadata_pushed"),
        "blob_uploaded": push_result.get("blob_uploaded"),
        "skipped": push_result.get("skipped"),
    }


async def push_project_artefacts_to_cloud(
    *,
    cloud_dir: Path,
    sync_port: ProjectSyncPort,
    project_id: str,
    client: CloudControlPlaneClient,
) -> dict[str, Any]:
    """Pousse métadonnées et blobs vers le control plane avec skip résilient."""
    metadata_pushed: list[str] = []
    blobs_uploaded: list[str] = []
    skipped: list[str] = []

    artefacts = sync_port.list_artefacts(project_id)
    for artefact in artefacts:
        artefact_id = str(artefact.get("id", ""))
        if not artefact_id:
            continue

        content = sync_port.read_blob(f"{project_id}/{artefact_id}")
        filename = str(artefact.get("name") or artefact_id)
        version = str(artefact.get("version") or "1.0.0")

        push_result = await push_single_artefact(
            client=client,
            project_id=project_id,
            artifact_id=artefact_id,
            version=version,
            filename=filename,
            content=content,
        )
        metadata_pushed.append(artefact_id)
        if push_result.get("skipped"):
            skipped.append(artefact_id)
        elif push_result.get("blob_uploaded"):
            blobs_uploaded.append(artefact_id)

    return {
        "metadata_pushed": metadata_pushed,
        "blobs_uploaded": blobs_uploaded,
        "skipped": skipped,
    }


async def pull_project_artefacts_from_cloud(
    *,
    cloud_dir: Path,
    sync_port: ProjectSyncPort,
    project_id: str,
    client: CloudControlPlaneClient,
) -> dict[str, Any]:
    """Télécharge les artefacts confirmés depuis le control plane vers le cache jetable.

    Stratégie :
    - ``not_confirmed`` : artefact distant sans blob confirmé → ignoré.
    - ``cache_up_to_date`` : version cache >= distante → ignoré.
    - version distante plus récente : téléchargement dans le cache (pas artefacts/ SoT).
    - Après téléchargement : vérification checksum/size si fournis par le control plane.
    """
    _ = sync_port
    from app.plugins.workproba_cloud.cache_service import (
        get_cached_artefact_version,
        write_artefact_to_cache,
    )

    pulled: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    remote = await client.list_sync_artefacts(project_id=project_id)
    items = remote.get("items") or []
    if not isinstance(items, list):
        return {"pulled": pulled, "skipped": skipped, "errors": ["invalid_remote_list"]}

    for item in items:
        if not isinstance(item, dict):
            continue
        artefact_db_id = item.get("id")
        artifact_id = str(item.get("artifactId") or item.get("filename") or "")
        if not isinstance(artefact_db_id, int) or not artifact_id:
            continue
        if not item.get("confirmedAt"):
            skipped.append(_skip_reason(artifact_id, "not_confirmed"))
            continue

        remote_version = item.get("version")
        remote_checksum = item.get("checksum")
        remote_checksum_str = str(remote_checksum) if remote_checksum else None
        remote_size = item.get("size")
        cached_version = get_cached_artefact_version(
            cloud_dir,
            project_id=project_id,
            artefact_id=artifact_id,
        )
        if cached_version and not _is_remote_newer(
            cached_version,
            str(remote_version) if remote_version else None,
        ):
            skipped.append(_skip_reason(artifact_id, "cache_up_to_date"))
            continue

        try:
            download = await client.request_download_url(artefact_db_id=artefact_db_id)
            url = download.get("url")
            if not isinstance(url, str) or not url.strip():
                errors.append(f"{artifact_id}: missing_download_url")
                continue
            content = await client.get_presigned_blob(url.strip())
            if remote_checksum_str:
                actual_checksum = _artifact_checksum(content)
                if actual_checksum != remote_checksum_str:
                    errors.append(f"{artifact_id}:checksum_mismatch")
                    continue
            if remote_size is not None:
                try:
                    expected_size = int(remote_size)
                except (TypeError, ValueError):
                    expected_size = -1
                if expected_size >= 0 and len(content) != expected_size:
                    errors.append(f"{artifact_id}: size_mismatch")
                    continue
            version = str(remote_version) if remote_version else "1.0.0"
            filename = str(item.get("filename") or artifact_id)
            write_artefact_to_cache(
                cloud_dir,
                project_id=project_id,
                artefact_id=artifact_id,
                version=version,
                filename=filename,
                content=content,
            )
            pulled.append(artifact_id)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{artifact_id}: {type(exc).__name__}: {exc}")

    return {"pulled": pulled, "skipped": skipped, "errors": errors}


async def list_artefact_sync_status(
    *,
    cloud_dir: Path,
    sync_port: ProjectSyncPort,
    project_id: str,
) -> list[dict[str, Any]]:
    """Statut de sync par document publié (local, mount, cloud confirmé)."""
    mount_files: set[str] = set()
    mount_path = cloud_storage.get_mount_path(cloud_dir)
    if mount_path:
        mount_root = Path(mount_path).expanduser() / "projects" / project_id
        if mount_root.is_dir():
            mount_files = {path.name for path in mount_root.iterdir() if path.is_file()}

    cloud_by_artifact: dict[str, dict[str, Any]] = {}
    if is_cloud_enrolled(cloud_dir):
        base_url = cloud_storage.get_control_plane_base_url(cloud_dir)
        if base_url:
            client = CloudControlPlaneClient(base_url=base_url, plugin_data_dir=cloud_dir)
            try:
                remote = await client.list_sync_artefacts(project_id=project_id)
                for item in remote.get("items") or []:
                    if not isinstance(item, dict):
                        continue
                    artifact_id = str(item.get("artifactId") or item.get("filename") or "")
                    if artifact_id:
                        cloud_by_artifact[artifact_id] = item
            except Exception:
                pass

    items: list[dict[str, Any]] = []
    for artefact in sync_port.list_artefacts(project_id):
        artefact_id = str(artefact.get("id") or "")
        if not artefact_id:
            continue
        remote = cloud_by_artifact.get(artefact_id, {})
        confirmed_at = remote.get("confirmedAt")
        cloud_confirmed = bool(confirmed_at)
        in_cloud = artefact_id in cloud_by_artifact
        items.append(
            {
                "id": artefact_id,
                "name": str(artefact.get("name") or artefact_id),
                "version": artefact.get("version"),
                "published": True,
                "mount_synced": artefact_id in mount_files,
                "cloud_confirmed": cloud_confirmed,
                "cloud_pending": in_cloud and not cloud_confirmed,
            }
        )
    return items
