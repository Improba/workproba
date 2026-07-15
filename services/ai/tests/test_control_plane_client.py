"""Tests CloudControlPlaneClient scaffold (T-V3-CP-1)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

import app.auth as authmod
import app.main as mainmod
from app.plugins.ports.managed_regards import create_personas_managed_port, sign_bundle_for_tests
from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD, PLUGIN_WORKPROBA_PERSONAS
from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient

INTERNAL_HEADERS = {"X-Internal-Secret": "desktop-dev-secret"}


@pytest.fixture(autouse=True)
def _patch_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)


def _layout(tmp_path: Path) -> tuple[Path, Path, Path]:
    app_data = tmp_path / "app_data"
    plugins = app_data / "plugins"
    cloud_dir = plugins / PLUGIN_WORKPROBA_CLOUD
    personas_dir = plugins / PLUGIN_WORKPROBA_PERSONAS
    cloud_dir.mkdir(parents=True)
    personas_dir.mkdir(parents=True)
    return cloud_dir, personas_dir, plugins


def _sample_bundle_dict() -> dict:
    return sign_bundle_for_tests(
        catalog_id="cloud-regards",
        version="2.0.0",
        name="Cloud Regards",
        personas=[
            {
                "id": "c01",
                "name": "Risk",
                "role": "Risques",
                "description": "Risque opérationnel",
                "system_prompt": "Tu es risk manager.",
                "avatar_color": "#AA5533",
                "avatar_icon": "alert-triangle",
            }
        ],
    ).to_dict()


@pytest.mark.asyncio
async def test_authenticate_bearer_persists_tokens(tmp_path: Path) -> None:
    cloud_dir, _, _ = _layout(tmp_path)
    client = CloudControlPlaneClient(
        base_url="https://cloud.example.test",
        plugin_data_dir=cloud_dir,
    )
    result = await client.authenticate(bearer_token="test-token", org_id="org-42")
    assert result["authenticated"] is True
    tokens = client.load_tokens()
    assert tokens["access_token"] == "test-token"
    assert tokens["org_id"] == "org-42"


@pytest.mark.asyncio
async def test_fetch_endpoints_with_mock_transport(tmp_path: Path) -> None:
    cloud_dir, _, _ = _layout(tmp_path)
    bundle = _sample_bundle_dict()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/catalogs/regards":
            return httpx.Response(200, json={"bundles": [bundle]})
        if request.url.path == "/catalogs/capabilities":
            return httpx.Response(200, json={"capabilities": ["workproba.personas"]})
        if request.url.path == "/policies":
            return httpx.Response(200, json={"project_sync": True})
        if request.url.path == "/presets/active":
            return httpx.Response(200, json={"preset_id": "enterprise"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://cloud.example.test",
        transport=transport,
    ) as http_client:
        client = CloudControlPlaneClient(
            base_url="https://cloud.example.test",
            plugin_data_dir=cloud_dir,
            http_client=http_client,
        )
        await client.authenticate(bearer_token="abc")
        regards = await client.fetch_regards_catalog(org_id="org-1")
        caps = await client.fetch_capabilities(org_id="org-1")
        policies = await client.fetch_policies(org_id="org-1")
        preset = await client.fetch_active_preset(device_id="dev-1")

    assert regards["bundles"][0]["catalog_id"] == "cloud-regards"
    assert "workproba.personas" in caps["capabilities"]
    assert policies["project_sync"] is True
    assert preset["preset_id"] == "enterprise"


@pytest.mark.asyncio
async def test_pull_and_install_regards(tmp_path: Path) -> None:
    cloud_dir, personas_dir, _ = _layout(tmp_path)
    bundle = _sample_bundle_dict()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/catalogs/regards":
            return httpx.Response(200, json={"bundles": [bundle]})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://cloud.example.test",
        transport=transport,
    ) as http_client:
        client = CloudControlPlaneClient(
            base_url="https://cloud.example.test",
            plugin_data_dir=cloud_dir,
            http_client=http_client,
        )
        await client.authenticate(bearer_token="abc")
        port = create_personas_managed_port(personas_dir)
        result = await client.pull_and_install_regards(port)

    assert result["count"] == 1
    assert result["activated"]["catalog_id"] == "cloud-regards"
    status = port.get_catalog_status()
    assert status["active"] is True


def test_cloud_enroll_http(tmp_path: Path) -> None:
    cloud_dir, _, _ = _layout(tmp_path)
    with TestClient(mainmod.app) as test_client:
        enroll_resp = test_client.post(
            "/plugins/cloud/enroll",
            json={
                "plugin_data_dir": str(cloud_dir),
                "base_url": "https://cloud.example.test",
                "bearer_token": "token-xyz",
                "org_id": "org-http",
            },
            headers=INTERNAL_HEADERS,
        )
        assert enroll_resp.status_code == 200
        assert enroll_resp.json()["authenticated"] is True


def test_cloud_sync_regards_http(tmp_path: Path) -> None:
    cloud_dir, personas_dir, _ = _layout(tmp_path)
    bundle = _sample_bundle_dict()

    async def fake_pull(
        self,
        managed_regards_port,
        *,
        org_id: str | None = None,
        activate: bool = True,
    ):
        from app.plugins.ports.managed_regards import SignedBundle

        signed = SignedBundle.from_dict(bundle)
        installed = managed_regards_port.install_catalog_version(signed)
        activated = managed_regards_port.activate_catalog(signed.catalog_id, signed.version)
        return {"installed": [installed], "activated": activated, "count": 1}

    with patch.object(CloudControlPlaneClient, "pull_and_install_regards", fake_pull):
        with TestClient(mainmod.app) as test_client:
            test_client.post(
                "/plugins/cloud/enroll",
                json={
                    "plugin_data_dir": str(cloud_dir),
                    "base_url": "https://cloud.example.test",
                    "bearer_token": "token-xyz",
                },
                headers=INTERNAL_HEADERS,
            )
            sync_resp = test_client.post(
                "/plugins/cloud/sync-regards",
                json={"plugin_data_dir": str(cloud_dir)},
                headers=INTERNAL_HEADERS,
            )
            assert sync_resp.status_code == 200
            assert sync_resp.json()["count"] == 1

    port = create_personas_managed_port(personas_dir)
    assert port.get_catalog_status()["catalog_id"] == "cloud-regards"
    assert not (cloud_dir / "managed").exists()
    assert (personas_dir / "managed" / "cloud-regards").exists()
