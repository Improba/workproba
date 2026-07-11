"""Tests snapshot/restauration des versions de fichiers (stockage canonique)."""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.auth as authmod
import app.main as mainmod
from app.local_client import LocalProjectClient
from app.versions import (
    file_path_hash,
    list_versions,
    load_manifest,
    restore_version,
    snapshot_before_overwrite,
    versions_dir_for_file,
)


@pytest.fixture(autouse=True)
def _patch_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)


def test_snapshot_creates_manifest_entry(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    ws_data = tmp_path / "ws_data"
    ws_data.mkdir()
    target = project / "contrat.md"
    target.write_text("version initiale", encoding="utf-8")

    entry = snapshot_before_overwrite(
        workspace_data_dir=ws_data,
        project_root=project,
        relative_path="contrat.md",
    )
    assert entry is not None
    assert entry["file_path"] == "contrat.md"
    assert "version_id" in entry

    version_dir = versions_dir_for_file(ws_data, "contrat.md")
    manifest_path = version_dir / "manifest.json"
    entries = load_manifest(manifest_path)
    assert len(entries) == 1
    snapshot_file = version_dir / f"{entries[0]['version_id']}.bin"
    assert snapshot_file.is_file()
    assert snapshot_file.read_text(encoding="utf-8") == "version initiale"


def test_file_path_hash_is_stable() -> None:
    assert file_path_hash("foo/bar.md") == file_path_hash("./foo/bar.md")


def test_snapshot_soft_fail_when_versions_unwritable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    ws_data = tmp_path / "ws_data"
    ws_data.mkdir()
    target = project / "note.txt"
    target.write_text("ancien", encoding="utf-8")
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")

    monkeypatch.setattr(
        "app.versions.versions_dir_for_file",
        lambda _ws, _path: blocker / "versions" / "hash",
    )

    entry = snapshot_before_overwrite(
        workspace_data_dir=ws_data,
        project_root=project,
        relative_path="note.txt",
    )
    assert entry is None


def test_generate_document_snapshots_before_overwrite(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    ws_data = tmp_path / "ws_data"
    ws_data.mkdir()
    (project / "rapport.md").write_text("ancien contenu", encoding="utf-8")
    client = LocalProjectClient(
        project_root=project,
        workspace_data_dir=ws_data,
    )
    payload = base64.b64encode(b"nouveau contenu").decode("ascii")

    asyncio.run(
        client.save_generated_document(
            tenant_id="t",
            project_id="p",
            session_id="sess-3",
            name="rapport.md",
            mime_type="text/markdown",
            content_base64=payload,
        )
    )

    assert (project / "rapport.md").read_text(encoding="utf-8") == "nouveau contenu"
    versions = list_versions(workspace_data_dir=ws_data, file_path="rapport.md")
    assert len(versions) == 1
    version_dir = versions_dir_for_file(ws_data, "rapport.md")
    snapshot_file = version_dir / f"{versions[0]['version_id']}.bin"
    assert snapshot_file.read_text(encoding="utf-8") == "ancien contenu"


def test_restore_round_trip(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    ws_data = tmp_path / "ws_data"
    ws_data.mkdir()
    target = project / "doc.txt"
    target.write_text("v1", encoding="utf-8")
    first = snapshot_before_overwrite(
        workspace_data_dir=ws_data,
        project_root=project,
        relative_path="doc.txt",
    )
    assert first is not None
    target.write_text("v2", encoding="utf-8")

    restore_version(
        workspace_data_dir=ws_data,
        project_root=project,
        file_path="doc.txt",
        version_id=str(first["version_id"]),
    )
    assert target.read_text(encoding="utf-8") == "v1"

    versions = list_versions(workspace_data_dir=ws_data, file_path="doc.txt")
    assert len(versions) == 2


def test_versions_http_list_and_restore(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    ws_data = tmp_path / "ws_data"
    ws_data.mkdir()
    target = project / "fichier.md"
    target.write_text("original", encoding="utf-8")
    entry = snapshot_before_overwrite(
        workspace_data_dir=ws_data,
        project_root=project,
        relative_path="fichier.md",
    )
    assert entry is not None
    target.write_text("modifié", encoding="utf-8")

    headers = {"X-Internal-Secret": "desktop-dev-secret"}
    with TestClient(mainmod.app) as client:
        list_resp = client.get(
            "/versions",
            params={
                "workspace_data_dir": str(ws_data),
                "file_path": "fichier.md",
            },
            headers=headers,
        )
        assert list_resp.status_code == 200
        versions = list_resp.json()["versions"]
        assert len(versions) == 1
        assert "Version créée" in versions[0]["label"] or "Version saved" in versions[0]["label"]

        restore_resp = client.post(
            "/versions/restore",
            json={
                "workspace_data_dir": str(ws_data),
                "project_path": str(project),
                "file_path": "fichier.md",
                "version_id": versions[0]["version_id"],
            },
            headers=headers,
        )
        assert restore_resp.status_code == 200
        assert restore_resp.json()["restored_path"] == "fichier.md"

    assert target.read_text(encoding="utf-8") == "original"
