"""Tests snapshot/restauration des versions de fichiers."""

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
    list_snapshots,
    load_manifest,
    restore_snapshot,
    snapshot_before_overwrite,
    versions_session_dir,
)


@pytest.fixture(autouse=True)
def _patch_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)


def test_snapshot_creates_manifest_entry(tmp_path: Path) -> None:
    target = tmp_path / "contrat.md"
    target.write_text("version initiale", encoding="utf-8")

    entry = snapshot_before_overwrite(
        project_root=tmp_path,
        session_id="sess-1",
        relative_path="contrat.md",
    )
    assert entry is not None
    assert entry["original_path"] == "contrat.md"
    assert entry["session_id"] == "sess-1"

    manifest_path = versions_session_dir(tmp_path, "sess-1") / "manifest.json"
    entries = load_manifest(manifest_path)
    assert len(entries) == 1
    assert entries[0]["snapshot_path"].startswith(".workproba/versions/sess-1/")
    snapshot_file = tmp_path / entries[0]["snapshot_path"]
    assert snapshot_file.is_file()
    assert snapshot_file.read_text(encoding="utf-8") == "version initiale"


def test_snapshot_soft_fail_when_versions_unwritable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "note.txt"
    target.write_text("ancien", encoding="utf-8")
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")

    monkeypatch.setattr(
        "app.versions.versions_session_dir",
        lambda _root, _session: blocker / "versions" / "sess-2",
    )

    entry = snapshot_before_overwrite(
        project_root=tmp_path,
        session_id="sess-2",
        relative_path="note.txt",
    )
    assert entry is None


def test_generate_document_snapshots_before_overwrite(tmp_path: Path) -> None:
    (tmp_path / "rapport.md").write_text("ancien contenu", encoding="utf-8")
    client = LocalProjectClient(project_root=tmp_path)
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

    assert (tmp_path / "rapport.md").read_text(encoding="utf-8") == "nouveau contenu"
    snapshots = list_snapshots(
        project_root=tmp_path,
        session_id="sess-3",
        file_path="rapport.md",
    )
    assert len(snapshots) == 1
    snapshot_file = tmp_path / snapshots[0]["snapshot_path"]
    assert snapshot_file.read_text(encoding="utf-8") == "ancien contenu"


def test_restore_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "doc.txt"
    target.write_text("v1", encoding="utf-8")
    first = snapshot_before_overwrite(
        project_root=tmp_path,
        session_id="sess-4",
        relative_path="doc.txt",
    )
    assert first is not None
    target.write_text("v2", encoding="utf-8")

    restore_snapshot(
        project_root=tmp_path,
        session_id="sess-4",
        snapshot_path=str(first["snapshot_path"]),
    )
    assert target.read_text(encoding="utf-8") == "v1"

    snapshots = list_snapshots(
        project_root=tmp_path,
        session_id="sess-4",
        file_path="doc.txt",
    )
    assert len(snapshots) == 2


def test_versions_http_list_and_restore(tmp_path: Path) -> None:
    target = tmp_path / "fichier.md"
    target.write_text("original", encoding="utf-8")
    entry = snapshot_before_overwrite(
        project_root=tmp_path,
        session_id="sess-http",
        relative_path="fichier.md",
    )
    assert entry is not None
    target.write_text("modifié", encoding="utf-8")

    headers = {"X-Internal-Secret": "desktop-dev-secret"}
    with TestClient(mainmod.app) as client:
        list_resp = client.get(
            "/versions",
            params={
                "project_path": str(tmp_path),
                "session_id": "sess-http",
                "file_path": "fichier.md",
            },
            headers=headers,
        )
        assert list_resp.status_code == 200
        snapshots = list_resp.json()["snapshots"]
        assert len(snapshots) == 1

        restore_resp = client.post(
            "/versions/restore",
            json={
                "project_path": str(tmp_path),
                "session_id": "sess-http",
                "snapshot_path": snapshots[0]["snapshot_path"],
            },
            headers=headers,
        )
        assert restore_resp.status_code == 200
        assert restore_resp.json()["restored_path"] == "fichier.md"

    assert target.read_text(encoding="utf-8") == "original"
