"""Tests plugin cloud (sync dossier local via ProjectSyncPort)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.auth as authmod
import app.main as mainmod
from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD
from app.plugins.workproba_cloud import storage as cloud_storage
from app.plugins.workproba_cloud.sync_access import open_sync_port_for_cloud
from app.plugins.workproba_projet import storage as projet_storage

INTERNAL_HEADERS = {"X-Internal-Secret": "desktop-dev-secret"}


@pytest.fixture(autouse=True)
def _patch_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)


def _layout(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    app_data = tmp_path / "app_data"
    plugins = app_data / "plugins"
    cloud_dir = plugins / PLUGIN_WORKPROBA_CLOUD
    projet_dir = plugins / "workproba.projet"
    cloud_dir.mkdir(parents=True)
    projet_dir.mkdir(parents=True)
    mount = tmp_path / "cloud_mount"
    mount.mkdir()
    project = projet_storage.create_project(projet_dir, "Contrats")
    project_id = str(project["id"])
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = workspace / "contrat.docx"
    source.write_text("contenu", encoding="utf-8")
    projet_storage.publish_artifact(
        plugin_data_dir=projet_dir,
        workspace_root=workspace,
        source_path="contrat.docx",
        project_id=project_id,
        name="contrat.docx",
    )
    return cloud_dir, projet_dir, mount, project_id


def test_cloud_config_and_status(tmp_path: Path) -> None:
    cloud_dir, _, mount, _ = _layout(tmp_path)
    cloud_storage.save_config(cloud_dir, {"mount_path": str(mount)})
    status = cloud_storage.status(cloud_dir)
    assert status["configured"] is True
    assert status["mount_path"] == str(mount)


def test_cloud_sync_copies_artefacts_via_port(tmp_path: Path) -> None:
    cloud_dir, _, mount, project_id = _layout(tmp_path)
    sync_port = open_sync_port_for_cloud(cloud_dir.parent)
    result = cloud_storage.sync_project(
        plugin_data_dir=cloud_dir,
        sync_port=sync_port,
        project_id=project_id,
        mount_path=str(mount),
    )
    assert "contrat.docx" in result["synced"]
    copied = mount / "projects" / project_id / "contrat.docx"
    assert copied.is_file()
    assert copied.read_text(encoding="utf-8") == "contenu"


def test_cloud_sync_requires_configuration(tmp_path: Path) -> None:
    cloud_dir, _, _, project_id = _layout(tmp_path)
    sync_port = open_sync_port_for_cloud(cloud_dir.parent)
    with pytest.raises(ValueError, match="cloud_not_configured"):
        cloud_storage.sync_project(
            plugin_data_dir=cloud_dir,
            sync_port=sync_port,
            project_id=project_id,
        )


def test_cloud_http_endpoints(tmp_path: Path) -> None:
    cloud_dir, _, mount, project_id = _layout(tmp_path)
    with TestClient(mainmod.app) as client:
        config_resp = client.post(
            "/plugins/cloud/config",
            json={
                "plugin_data_dir": str(cloud_dir),
                "mount_path": str(mount),
            },
            headers=INTERNAL_HEADERS,
        )
        assert config_resp.status_code == 200
        assert config_resp.json()["ok"] is True

        status_resp = client.get(
            "/plugins/cloud/status",
            params={"plugin_data_dir": str(cloud_dir)},
            headers=INTERNAL_HEADERS,
        )
        assert status_resp.status_code == 200
        assert status_resp.json()["configured"] is True

        sync_resp = client.post(
            "/plugins/cloud/sync",
            json={
                "plugin_data_dir": str(cloud_dir),
                "project_id": project_id,
                "mount_path": str(mount),
            },
            headers=INTERNAL_HEADERS,
        )
        assert sync_resp.status_code == 200
        assert "contrat.docx" in sync_resp.json()["synced"]


def test_cloud_sync_http_forbidden_without_project_sync(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.plugins.workproba_cloud import sync_access

    def deny_port(_plugins_root: Path):
        raise PermissionError("Missing permission: project:sync")

    monkeypatch.setattr(sync_access, "open_sync_port_for_cloud", deny_port)

    cloud_dir, _, mount, project_id = _layout(tmp_path)
    with TestClient(mainmod.app) as client:
        sync_resp = client.post(
            "/plugins/cloud/sync",
            json={
                "plugin_data_dir": str(cloud_dir),
                "project_id": project_id,
                "mount_path": str(mount),
            },
            headers=INTERNAL_HEADERS,
        )
        assert sync_resp.status_code == 403
        assert "project:sync" in sync_resp.json()["detail"]
