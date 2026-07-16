"""Cache jetable pour ouverture à la demande des artefacts cloud."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient

_INVALID_PATH_CHARS = ("..", "/", "\\")


def _artifact_checksum(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _sanitize_path_segment(value: str, field: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"invalid_{field}")
    for token in _INVALID_PATH_CHARS:
        if token in cleaned:
            raise ValueError(f"invalid_{field}")
    return cleaned


def _safe_filename(filename: str, fallback: str) -> str:
    cleaned = Path(filename).name.strip()
    safe = cleaned or fallback
    return _sanitize_path_segment(safe, "filename")


def _parse_version(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for segment in version.split("."):
        try:
            parts.append(int(segment))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def cache_artefact_path(
    cloud_dir: Path,
    *,
    project_id: str,
    artifact_id: str,
    version: str,
    filename: str,
) -> Path:
    safe_project_id = _sanitize_path_segment(project_id, "project_id")
    safe_artefact_id = _sanitize_path_segment(artifact_id, "artifact_id")
    safe_version = version.replace("/", "_").strip() or "0"
    safe_name = _safe_filename(filename, artifact_id)
    return (
        cloud_dir
        / "cache"
        / safe_project_id
        / safe_artefact_id
        / f"v{safe_version}"
        / safe_name
    )


def write_artefact_to_cache(
    cloud_dir: Path,
    *,
    project_id: str,
    artefact_id: str,
    version: str,
    filename: str,
    content: bytes,
) -> Path:
    """Écrit un artefact téléchargé dans le cache jetable."""
    cache_path = cache_artefact_path(
        cloud_dir,
        project_id=project_id,
        artifact_id=artefact_id,
        version=version,
        filename=filename,
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(content)
    return cache_path


def get_cached_artefact_version(
    cloud_dir: Path,
    *,
    project_id: str,
    artefact_id: str,
) -> str | None:
    """Retourne la version la plus récente présente dans le cache local."""
    safe_project_id = _sanitize_path_segment(project_id, "project_id")
    safe_artefact_id = _sanitize_path_segment(artefact_id, "artefact_id")
    base = cloud_dir / "cache" / safe_project_id / safe_artefact_id
    if not base.is_dir():
        return None
    versions: list[str] = []
    for version_dir in base.iterdir():
        if version_dir.is_dir() and version_dir.name.startswith("v"):
            versions.append(version_dir.name[1:])
    if not versions:
        return None
    return max(versions, key=_parse_version)


def _matches_artefact_id(item: dict[str, Any], artefact_id: str) -> bool:
    candidates = (
        item.get("artifactId"),
        item.get("filename"),
        item.get("id"),
    )
    return any(str(value) == artefact_id for value in candidates if value is not None)


async def open_cloud_artefact_to_cache(
    *,
    cloud_dir: Path,
    project_id: str,
    artefact_id: str,
    client: CloudControlPlaneClient,
) -> dict[str, Any]:
    """Télécharge un artefact confirmé dans le cache jetable et retourne son chemin local."""
    remote = await client.list_sync_artefacts(project_id=project_id)
    items = remote.get("items") or []
    if not isinstance(items, list):
        raise ValueError("invalid_remote_list")

    selected: dict[str, Any] | None = None
    for item in items:
        if isinstance(item, dict) and _matches_artefact_id(item, artefact_id):
            selected = item
            break
    if selected is None:
        raise ValueError("artefact_not_found")

    artefact_db_id = selected.get("id")
    artifact_id = str(selected.get("artifactId") or selected.get("filename") or artefact_id)
    if not isinstance(artefact_db_id, int):
        raise ValueError("artefact_not_found")
    if not selected.get("confirmedAt"):
        raise ValueError("artefact_not_confirmed")

    version = str(selected.get("version") or "1.0.0")
    filename = _safe_filename(
        str(selected.get("filename") or artifact_id),
        artifact_id,
    )
    cache_path = cache_artefact_path(
        cloud_dir,
        project_id=project_id,
        artifact_id=artifact_id,
        version=version,
        filename=filename,
    )
    if cache_path.is_file():
        return {
            "local_path": str(cache_path.resolve()),
            "artefact_id": artifact_id,
            "version": version,
            "filename": filename,
        }

    download = await client.request_download_url(artefact_db_id=artefact_db_id)
    url = download.get("url")
    if not isinstance(url, str) or not url.strip():
        raise ValueError("missing_download_url")

    content = await client.get_presigned_blob(url.strip())
    remote_checksum = selected.get("checksum")
    if remote_checksum:
        actual_checksum = _artifact_checksum(content)
        if actual_checksum != str(remote_checksum):
            raise ValueError("checksum_mismatch")

    remote_size = selected.get("size")
    if remote_size is not None:
        try:
            expected_size = int(remote_size)
        except (TypeError, ValueError):
            expected_size = -1
        if expected_size >= 0 and len(content) != expected_size:
            raise ValueError("size_mismatch")

    write_artefact_to_cache(
        cloud_dir,
        project_id=project_id,
        artefact_id=artifact_id,
        version=version,
        filename=filename,
        content=content,
    )
    return {
        "local_path": str(cache_path.resolve()),
        "artefact_id": artifact_id,
        "version": version,
        "filename": filename,
    }


def find_cached_artefact_path(
    cloud_dir: Path,
    *,
    project_id: str,
    artefact_id: str,
    cache_path: str | None = None,
) -> Path:
    """Retourne le fichier cache le plus récent pour un artefact cloud."""
    cache_root = (cloud_dir / "cache").resolve()
    if cache_path:
        path = Path(cache_path).expanduser().resolve()
        if not path.is_file():
            raise ValueError("cache_not_found")
        if not path.is_relative_to(cache_root):
            raise ValueError("cache_path_outside_cache")
        return path

    safe_project_id = _sanitize_path_segment(project_id, "project_id")
    safe_artefact_id = _sanitize_path_segment(artefact_id, "artefact_id")
    candidates: list[Path] = []
    base = cloud_dir / "cache" / safe_project_id / safe_artefact_id
    if base.is_dir():
        for version_dir in base.iterdir():
            if version_dir.is_dir():
                candidates.extend(item for item in version_dir.iterdir() if item.is_file())
    if not candidates:
        raise ValueError("cache_not_found")
    return max(candidates, key=lambda item: item.stat().st_mtime)


def has_cached_artefact(
    cloud_dir: Path,
    *,
    project_id: str,
    artefact_id: str,
) -> bool:
    try:
        find_cached_artefact_path(
            cloud_dir,
            project_id=project_id,
            artefact_id=artefact_id,
        )
    except ValueError:
        return False
    return True


async def republish_cloud_artefact_from_cache(
    *,
    cloud_dir: Path,
    project_id: str,
    artefact_id: str,
    client: CloudControlPlaneClient,
    cache_path: str | None = None,
) -> dict[str, Any]:
    """Republie le contenu du cache local vers le cloud avec bump de version."""
    from app.plugins.workproba_cloud.sync_service import publish_shared_artefact_to_cloud

    path = find_cached_artefact_path(
        cloud_dir,
        project_id=project_id,
        artefact_id=artefact_id,
        cache_path=cache_path,
    )
    content = path.read_bytes()
    filename = path.name
    return await publish_shared_artefact_to_cloud(
        cloud_dir=cloud_dir,
        client=client,
        project_id=project_id,
        filename=filename,
        content=content,
    )
