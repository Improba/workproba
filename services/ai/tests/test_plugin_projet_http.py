"""Tests HTTP endpoints plugin projet."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.auth as authmod
import app.main as mainmod


@pytest.fixture(autouse=True)
def _patch_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)


@pytest.fixture
def plugin_dir(tmp_path: Path) -> Path:
    path = tmp_path / "plugins" / "workproba.projet"
    path.mkdir(parents=True)
    return path


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "note.txt").write_text("hello", encoding="utf-8")
    return ws


def test_projet_projects_crud(plugin_dir: Path) -> None:
    with TestClient(mainmod.app) as client:
        list_resp = client.get(
            "/plugins/projet/projects",
            params={"plugin_data_dir": str(plugin_dir)},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert list_resp.status_code == 200
        assert list_resp.json()["projects"] == []

        create_resp = client.post(
            "/plugins/projet/projects",
            json={"plugin_data_dir": str(plugin_dir), "name": "Mon projet"},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert create_resp.status_code == 200
        project = create_resp.json()["project"]
        assert project["name"] == "Mon projet"

        list_resp2 = client.get(
            "/plugins/projet/projects",
            params={"plugin_data_dir": str(plugin_dir)},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert len(list_resp2.json()["projects"]) == 1


def test_projet_publish_and_list_artefacts(
    plugin_dir: Path,
    workspace: Path,
) -> None:
    with TestClient(mainmod.app) as client:
        project = client.post(
            "/plugins/projet/projects",
            json={"plugin_data_dir": str(plugin_dir), "name": "P1"},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        ).json()["project"]

        publish_resp = client.post(
            "/plugins/projet/publish",
            json={
                "plugin_data_dir": str(plugin_dir),
                "workspace_data_dir": str(workspace),
                "source_path": "note.txt",
                "project_id": project["id"],
                "name": "note.txt",
            },
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert publish_resp.status_code == 200
        artefact = publish_resp.json()["artefact"]
        assert artefact["name"] == "note.txt"

        artefacts_resp = client.get(
            "/plugins/projet/artefacts",
            params={
                "plugin_data_dir": str(plugin_dir),
                "project_id": project["id"],
            },
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert artefacts_resp.status_code == 200
        names = [item["name"] for item in artefacts_resp.json()["artefacts"]]
        assert "note.txt" in names


def test_projet_publish_path_traversal(
    plugin_dir: Path,
    workspace: Path,
) -> None:
    with TestClient(mainmod.app) as client:
        project = client.post(
            "/plugins/projet/projects",
            json={"plugin_data_dir": str(plugin_dir), "name": "P1"},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        ).json()["project"]

        resp = client.post(
            "/plugins/projet/publish",
            json={
                "plugin_data_dir": str(plugin_dir),
                "workspace_data_dir": str(workspace),
                "source_path": "../etc/passwd",
                "project_id": project["id"],
                "name": "passwd",
            },
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert resp.status_code == 403


def test_projet_endpoints_require_secret(plugin_dir: Path) -> None:
    with TestClient(mainmod.app) as client:
        resp = client.get(
            "/plugins/projet/projects",
            params={"plugin_data_dir": str(plugin_dir)},
        )
        assert resp.status_code == 401
