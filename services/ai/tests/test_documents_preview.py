"""Tests endpoint /documents/preview."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient
from openpyxl import Workbook

import app.auth as authmod
import app.main as mainmod


@pytest.fixture(autouse=True)
def _loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)


def _headers() -> dict[str, str]:
    return {"X-Internal-Secret": "desktop-dev-secret"}


def test_preview_docx(tmp_path: Path) -> None:
    doc = Document()
    doc.add_heading("Titre", level=1)
    doc.add_paragraph("Corps")
    path = tmp_path / "note.docx"
    doc.save(path)

    with TestClient(mainmod.app) as client:
        resp = client.get(
            "/documents/preview",
            params={
                "path": "note.docx",
                "workspace_data_dir": str(tmp_path),
                "project_path": str(tmp_path),
            },
            headers=_headers(),
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "docx"
    assert "<h1>Titre</h1>" in data["html"]
    assert "Corps" in data["html"]


def test_preview_xlsx(tmp_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["A", "B"])
    ws.append([1, 2])
    path = tmp_path / "data.xlsx"
    wb.save(path)

    with TestClient(mainmod.app) as client:
        resp = client.get(
            "/documents/preview",
            params={
                "path": "data.xlsx",
                "workspace_data_dir": str(tmp_path),
                "project_path": str(tmp_path),
            },
            headers=_headers(),
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "xlsx"
    assert "<table>" in data["html"]
    assert "A" in data["html"]


def test_preview_rejects_prefix_traversal(tmp_path: Path) -> None:
    """Bloque /tmp/foo-bar quand base=/tmp/foo (startswith insuffisant)."""
    base = tmp_path / "foo"
    base.mkdir()
    sibling = tmp_path / "foo-bar"
    sibling.mkdir()
    secret = sibling / "secret.txt"
    secret.write_text("secret", encoding="utf-8")

    with TestClient(mainmod.app) as client:
        resp = client.get(
            "/documents/preview",
            params={
                "path": "../foo-bar/secret.txt",
                "workspace_data_dir": str(tmp_path),
                "project_path": str(base),
            },
            headers=_headers(),
        )
    assert resp.status_code == 403


def test_preview_rejects_path_traversal(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")

    with TestClient(mainmod.app) as client:
        resp = client.get(
            "/documents/preview",
            params={
                "path": "../outside.txt",
                "workspace_data_dir": str(tmp_path),
                "project_path": str(tmp_path),
            },
            headers=_headers(),
        )
    assert resp.status_code == 403


def test_preview_separate_project_and_data_dirs(tmp_path: Path) -> None:
    """Desktop : folder_path et data_dir (.workproba) sont des chemins distincts."""
    data_dir = tmp_path / "data"
    project_dir = tmp_path / "project"
    data_dir.mkdir()
    project_dir.mkdir()
    doc = Document()
    doc.add_paragraph("Hello")
    doc.save(project_dir / "note.docx")

    with TestClient(mainmod.app) as client:
        resp = client.get(
            "/documents/preview",
            params={
                "path": "note.docx",
                "workspace_data_dir": str(data_dir),
                "project_path": str(project_dir),
            },
            headers=_headers(),
        )
    assert resp.status_code == 200
    assert "Hello" in resp.json()["html"]


def test_preview_image_type(tmp_path: Path) -> None:
    img = tmp_path / "pic.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")

    with TestClient(mainmod.app) as client:
        resp = client.get(
            "/documents/preview",
            params={
                "path": "pic.png",
                "workspace_data_dir": str(tmp_path),
                "project_path": str(tmp_path),
            },
            headers=_headers(),
        )
    assert resp.status_code == 200
    assert resp.json()["type"] == "image"
