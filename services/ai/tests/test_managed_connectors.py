"""Tests for managed connector invoke path (Mode A)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.agent.effects import classify_effect
from app.plugins.ports.remote_capability_gateway import (
    HttpRemoteCapabilityGateway,
    IdentityDelegation,
    clear_remote_capability_audit_log,
    remote_capability_audit_log,
)
from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD
from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient


def test_classify_invoke_managed_connector_is_external_send() -> None:
    proposal = classify_effect(
        "invoke_managed_connector",
        {"connector_id": "echo"},
        permissions_network=True,
    )
    assert proposal is not None
    assert proposal.effect == "external_send"
    assert proposal.protections.network_used is True
    assert proposal.protections.external_send is True
    assert proposal.targets == ["echo"]


@pytest.mark.asyncio
async def test_http_gateway_posts_connectors_echo(tmp_path: Path) -> None:
    clear_remote_capability_audit_log()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/connectors/echo/invoke"
        assert request.headers.get("Authorization") == "Bearer tok-device"
        body = json.loads(request.content.decode("utf-8"))
        assert body["payload"] == {"ping": True}
        assert body["identity"]["subject_id"] == "dev-1"
        return httpx.Response(
            200,
            json={
                "ok": True,
                "connectorId": "echo",
                "result": {"echo": {"ping": True}, "hasSecret": False, "secretKeys": []},
                "journalId": "j-1",
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="https://cloud.test")
    gateway = HttpRemoteCapabilityGateway(
        base_url="https://cloud.test",
        caller_plugin_id=PLUGIN_WORKPROBA_CLOUD,
        app_data_dir=tmp_path / "app_data",
        allowed_capability_ids=frozenset({"echo"}),
        http_client=client,
    )
    result = await gateway.invoke_remote(
        "echo",
        {"ping": True},
        IdentityDelegation(
            subject_id="dev-1",
            org_id="org-a",
            access_token="tok-device",
        ),
    )
    assert result["ok"] is True
    assert result["journalId"] == "j-1"
    assert any(e["op"] == "invoke_remote" for e in remote_capability_audit_log())


@pytest.mark.asyncio
async def test_control_plane_client_invoke_connector(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "cloud"
    plugin_dir.mkdir()
    client_holder: dict[str, CloudControlPlaneClient] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/connectors/ihora.shaped/invoke":
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "connectorId": "ihora.shaped",
                    "result": {"action": "list_absences", "absences": []},
                    "journalId": "j-2",
                },
            )
        return httpx.Response(404, json={"message": "not found"})

    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url="https://cloud.test")
    client = CloudControlPlaneClient(
        base_url="https://cloud.test",
        plugin_data_dir=plugin_dir,
        http_client=http,
    )
    client.save_tokens({"access_token": "tok", "org_id": "org-a", "device_id": "dev-1"})
    client_holder["c"] = client

    result = await client.invoke_connector(
        "ihora.shaped",
        payload={"action": "list_absences"},
        subject_id="dev-1",
        org_id="org-a",
    )
    assert result["ok"] is True
    assert result["connectorId"] == "ihora.shaped"


@pytest.mark.asyncio
async def test_fetch_allowed_connector_ids_returns_ids(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "cloud"
    plugin_dir.mkdir()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/connectors":
            return httpx.Response(
                200,
                json={
                    "connectors": [
                        {"id": "echo", "name": "Echo"},
                        {"id": "ihora.shaped", "name": "Ihora"},
                    ],
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url="https://cloud.test")
    client = CloudControlPlaneClient(
        base_url="https://cloud.test",
        plugin_data_dir=plugin_dir,
        http_client=http,
    )
    client.save_tokens({"access_token": "tok", "device_id": "dev-1"})

    allowed = await client.fetch_allowed_connector_ids()
    assert allowed == frozenset({"echo", "ihora.shaped"})


@pytest.mark.asyncio
async def test_fetch_allowed_connector_ids_empty_list(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "cloud"
    plugin_dir.mkdir()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/connectors":
            return httpx.Response(200, json={"connectors": []})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url="https://cloud.test")
    client = CloudControlPlaneClient(
        base_url="https://cloud.test",
        plugin_data_dir=plugin_dir,
        http_client=http,
    )
    client.save_tokens({"access_token": "tok", "device_id": "dev-1"})

    allowed = await client.fetch_allowed_connector_ids()
    assert allowed == frozenset()


@pytest.mark.asyncio
async def test_fetch_allowed_connector_ids_401_raises_permission_error(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "cloud"
    plugin_dir.mkdir()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/connectors":
            return httpx.Response(401, json={"message": "invalid_device_token"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url="https://cloud.test")
    client = CloudControlPlaneClient(
        base_url="https://cloud.test",
        plugin_data_dir=plugin_dir,
        http_client=http,
    )
    client.save_tokens({"access_token": "bad", "device_id": "dev-1"})

    with pytest.raises(PermissionError, match="invalid_device_token"):
        await client.fetch_allowed_connector_ids()


def test_cloud_list_connectors_not_enrolled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.auth as authmod
    from fastapi.testclient import TestClient

    import app.main as mainmod
    from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD

    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)

    with TestClient(mainmod.app) as test_client:
        resp = test_client.get(
            "/plugins/cloud/connectors",
            params={"plugin_data_dir": str(cloud_dir)},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["connectors"] == []
        assert body["enrolled"] is False


def test_cloud_list_connectors_bearer_without_device_returns_403(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json

    import app.auth as authmod
    from fastapi.testclient import TestClient

    import app.main as mainmod
    from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD

    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    config = {
        "base_url": "https://cloud.test",
        "tokens": {"access_token": "stub-bearer", "org_id": "org-a"},
    }
    (cloud_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")

    with TestClient(mainmod.app) as test_client:
        resp = test_client.get(
            "/plugins/cloud/connectors",
            params={"plugin_data_dir": str(cloud_dir)},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert resp.status_code == 403
        detail = resp.json()["detail"]
        assert "invitation" in detail.lower() or "code" in detail.lower()
