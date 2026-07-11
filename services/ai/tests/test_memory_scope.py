"""Tests mémoire : scope user (global) vs project, et cohérence inter-espaces."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.auth as authmod
import app.main as mainmod


@pytest.fixture(autouse=True)
def _patch_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)


def _make_workspace(app_data: Path, ws_id: str) -> Path:
    ws = app_data / "workspaces" / ws_id
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def test_memory_add_and_list_per_scope(tmp_path: Path) -> None:
    app_data = tmp_path / "workproba-appdata"
    ws = _make_workspace(app_data, "ws1")

    with TestClient(mainmod.app) as client:
        # Ajout d'un souvenir projet
        r = client.post(
            "/memory/add",
            json={
                "workspace_data_dir": str(ws),
                "memory_scope": "project",
                "content": "Le budget projet est de 120k€",
            },
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert r.status_code == 200, r.text
        project_mem = r.json()["memory"]
        assert project_mem["content"] == "Le budget projet est de 120k€"

        # Ajout d'un souvenir user (global)
        r = client.post(
            "/memory/add",
            json={
                "workspace_data_dir": str(ws),
                "memory_scope": "user",
                "content": "L'utilisateur préfère les réponses concises",
            },
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert r.status_code == 200, r.text

        # Liste projet -> 1 souvenir
        r = client.get(
            "/memory/items",
            params={"workspace_data_dir": str(ws), "memory_scope": "project"},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert r.status_code == 200
        project_items = r.json()["memories"]
        assert len(project_items) == 1
        assert project_items[0]["content"] == "Le budget projet est de 120k€"

        # Liste user -> 1 souvenir
        r = client.get(
            "/memory/items",
            params={"workspace_data_dir": str(ws), "memory_scope": "user"},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert r.status_code == 200
        user_items = r.json()["memories"]
        assert len(user_items) == 1
        assert user_items[0]["content"] == "L'utilisateur préfère les réponses concises"


def test_user_memory_is_shared_across_workspaces(tmp_path: Path) -> None:
    """La mémoire user est globale : un souvenir ajouté depuis ws1 est visible
    depuis ws2 (cohérence inter-espaces). La mémoire projet reste isolée."""
    app_data = tmp_path / "workproba-appdata"
    ws1 = _make_workspace(app_data, "ws1")
    ws2 = _make_workspace(app_data, "ws2")

    with TestClient(mainmod.app) as client:
        # Ajout user depuis ws1
        client.post(
            "/memory/add",
            json={
                "workspace_data_dir": str(ws1),
                "memory_scope": "user",
                "content": "Profil user : data scientist",
            },
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        # Ajout projet sur ws1
        client.post(
            "/memory/add",
            json={
                "workspace_data_dir": str(ws1),
                "memory_scope": "project",
                "content": "ws1 specifique",
            },
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )

        # Depuis ws2 : user mémoire visible, project mémoire vide
        r = client.get(
            "/memory/items",
            params={"workspace_data_dir": str(ws2), "memory_scope": "user"},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        user_from_ws2 = r.json()["memories"]
        assert any(m["content"] == "Profil user : data scientist" for m in user_from_ws2)

        r = client.get(
            "/memory/items",
            params={"workspace_data_dir": str(ws2), "memory_scope": "project"},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert r.json()["memories"] == []

        # Le souvenir user vit dans le dossier user/ global, pas dans ws1
        assert (app_data / "user" / "memory.db").is_file()


def test_memory_search_all_merges_scopes(tmp_path: Path) -> None:
    app_data = tmp_path / "workproba-appdata"
    ws = _make_workspace(app_data, "ws1")

    with TestClient(mainmod.app) as client:
        client.post(
            "/memory/add",
            json={
                "workspace_data_dir": str(ws),
                "memory_scope": "user",
                "content": "Pref Python",
            },
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        client.post(
            "/memory/add",
            json={
                "workspace_data_dir": str(ws),
                "memory_scope": "project",
                "content": "Projet Python API",
            },
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )

        r = client.get(
            "/memory/search",
            params={
                "workspace_data_dir": str(ws),
                "memory_scope": "all",
                "query": "Python",
            },
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert r.status_code == 200
        results = r.json()["results"]
        scopes = {hit.get("memory_scope") for hit in results}
        assert scopes == {"user", "project"}


def test_memory_forget_by_scope(tmp_path: Path) -> None:
    app_data = tmp_path / "workproba-appdata"
    ws = _make_workspace(app_data, "ws1")

    with TestClient(mainmod.app) as client:
        r = client.post(
            "/memory/add",
            json={
                "workspace_data_dir": str(ws),
                "memory_scope": "user",
                "content": "À oublier",
            },
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        mem_id = r.json()["memory"]["id"]

        # Oubli scope user
        r = client.post(
            "/memory/forget",
            json={
                "workspace_data_dir": str(ws),
                "memory_scope": "user",
                "memory_id": mem_id,
            },
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert r.status_code == 200

        # Le souvenir n'est plus listé
        r = client.get(
            "/memory/items",
            params={"workspace_data_dir": str(ws), "memory_scope": "user"},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert all(m["id"] != mem_id for m in r.json()["memories"])

        # Oublier un souvenir user depuis un autre workspace : introuvable car
        # l'ID n'existe pas dans le store user global -> 404 cohérent.
        ws2 = _make_workspace(app_data, "ws2")
        r = client.post(
            "/memory/forget",
            json={
                "workspace_data_dir": str(ws2),
                "memory_scope": "user",
                "memory_id": "does_not_exist",
            },
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert r.status_code == 404


def test_memory_clear_user_scope(tmp_path: Path) -> None:
    app_data = tmp_path / "workproba-appdata"
    ws = _make_workspace(app_data, "ws1")

    with TestClient(mainmod.app) as client:
        client.post(
            "/memory/add",
            json={
                "workspace_data_dir": str(ws),
                "memory_scope": "user",
                "content": "À effacer",
            },
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        r = client.request(
            "DELETE",
            "/memory",
            json={
                "workspace_data_dir": str(ws),
                "memory_scope": "user",
                "scope": "all",
                "confirmed": True,
            },
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert r.status_code == 200

        r = client.get(
            "/memory/items",
            params={"workspace_data_dir": str(ws), "memory_scope": "user"},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert r.json()["memories"] == []
