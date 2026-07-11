"""Tests endpoint /documents/preview-change."""

from __future__ import annotations

from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient

import app.auth as authmod
import app.main as mainmod
from app.documents.preview_change import build_line_diff_html


@pytest.fixture(autouse=True)
def _loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)


def _headers() -> dict[str, str]:
    return {"X-Internal-Secret": "desktop-dev-secret"}


def test_build_line_diff_html_marks_add_and_del() -> None:
    html = build_line_diff_html("ligne A\n", "ligne B\n")
    assert "wp-diff-add" in html
    assert "wp-diff-del" in html
    assert "ligne B" in html
    assert "ligne A" in html


def test_preview_change_text_file(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    ws_data = tmp_path / "ws_data"
    ws_data.mkdir()
    (project / "note.md").write_text("ancien\nligne 2", encoding="utf-8")

    with TestClient(mainmod.app) as client:
        resp = client.post(
            "/documents/preview-change",
            json={
                "workspace_data_dir": str(ws_data),
                "project_path": str(project),
                "file_path": "note.md",
                "proposed_content": "nouveau\nligne 2",
            },
            headers=_headers(),
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_binary"] is False
    assert data["is_new"] is False
    assert "wp-diff-add" in data["diff_html"]
    assert "nouveau" in data["diff_html"]


def test_preview_change_new_file(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    ws_data = tmp_path / "ws_data"
    ws_data.mkdir()

    with TestClient(mainmod.app) as client:
        resp = client.post(
            "/documents/preview-change",
            json={
                "workspace_data_dir": str(ws_data),
                "project_path": str(project),
                "file_path": "nouveau.txt",
                "proposed_content": "contenu",
            },
            headers=_headers(),
        )
    assert resp.status_code == 200
    assert resp.json()["is_new"] is True


def test_preview_change_binary_docx(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    ws_data = tmp_path / "ws_data"
    ws_data.mkdir()
    doc = Document()
    doc.add_paragraph("Corps")
    doc.save(project / "rapport.docx")

    with TestClient(mainmod.app) as client:
        resp = client.post(
            "/documents/preview-change",
            json={
                "workspace_data_dir": str(ws_data),
                "project_path": str(project),
                "file_path": "rapport.docx",
                "proposed_content": "ignored",
            },
            headers=_headers(),
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_binary"] is True
    assert data["diff_html"] == ""
    assert data["message"]


def test_preview_change_rejects_traversal(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    ws_data = tmp_path / "ws_data"
    ws_data.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")

    with TestClient(mainmod.app) as client:
        resp = client.post(
            "/documents/preview-change",
            json={
                "workspace_data_dir": str(ws_data),
                "project_path": str(project),
                "file_path": "../secret.txt",
                "proposed_content": "hack",
            },
            headers=_headers(),
        )
    assert resp.status_code == 403
