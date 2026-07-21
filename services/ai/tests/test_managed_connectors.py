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
        assert "identity" not in body
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
            body = json.loads(request.content.decode("utf-8"))
            assert "subject_id" not in body.get("identity", {})
            assert "org_id" not in body.get("identity", {})
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


def test_cloud_list_connectors_bearer_without_device_id_ok(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bearer enroll sans device_id local : DeviceBearer suffit pour lister."""
    import json

    import app.auth as authmod
    from fastapi.testclient import TestClient

    import app.main as mainmod
    from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD
    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient

    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    config = {
        "base_url": "https://cloud.test",
        "tokens": {"access_token": "stub-bearer", "org_id": "org-a"},
    }
    (cloud_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")

    async def fake_list(self: CloudControlPlaneClient) -> dict:
        return {
            "connectors": [
                {
                    "id": "c1",
                    "name": "Conn",
                    "runtime": "managed",
                    "description": "",
                }
            ]
        }

    monkeypatch.setattr(CloudControlPlaneClient, "list_connectors", fake_list)

    with TestClient(mainmod.app) as test_client:
        resp = test_client.get(
            "/plugins/cloud/connectors",
            params={"plugin_data_dir": str(cloud_dir)},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["enrolled"] is True
        assert len(body["connectors"]) == 1
        assert body["connectors"][0]["id"] == "c1"


def test_cloud_llm_quota_not_enrolled(
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
            "/plugins/cloud/llm-quota",
            params={"plugin_data_dir": str(cloud_dir)},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["enrolled"] is False
        assert body["enabled"] is False


def test_cloud_llm_quota_bearer_enroll_without_device_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L'enrôlement bearer n'écrit pas device_id : le quota doit quand même passer."""
    import app.auth as authmod
    from fastapi.testclient import TestClient

    import app.main as mainmod
    from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD
    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient

    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    (cloud_dir / "config.json").write_text(
        '{"base_url": "https://cloud.example.com"}',
        encoding="utf-8",
    )
    client = CloudControlPlaneClient(
        base_url="https://cloud.example.com",
        plugin_data_dir=cloud_dir,
    )
    client.save_tokens({"access_token": "tok", "org_id": "org-a"})

    async def fake_quota(self: CloudControlPlaneClient) -> dict:
        return {
            "enabled": True,
            "periodKey": "2026-07",
            "tokensUsed": 10,
            "tokensLimit": 1000,
            "requestsCount": 1,
            "requestsLimit": 100,
            "remainingTokens": 990,
            "remainingRequests": 99,
        }

    monkeypatch.setattr(CloudControlPlaneClient, "get_llm_quota", fake_quota)

    with TestClient(mainmod.app) as test_client:
        resp = test_client.get(
            "/plugins/cloud/llm-quota",
            params={"plugin_data_dir": str(cloud_dir)},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["enrolled"] is True
        assert body["enabled"] is True
        assert body["remaining_tokens"] == 990


def test_managed_connector_enabled_roundtrip(tmp_path: Path) -> None:
    from app.plugins.workproba_cloud import storage as cloud_storage

    cloud_dir = tmp_path / "cloud"
    cloud_dir.mkdir()
    assert cloud_storage.is_managed_connector_enabled(cloud_dir, "ihora") is True
    cloud_storage.set_managed_connector_enabled(cloud_dir, "ihora", enabled=False)
    assert cloud_storage.is_managed_connector_enabled(cloud_dir, "ihora") is False
    cloud_storage.set_managed_connector_enabled(cloud_dir, "ihora", enabled=True)
    assert cloud_storage.is_managed_connector_enabled(cloud_dir, "ihora") is True


def test_managed_connector_empty_id_not_enabled(tmp_path: Path) -> None:
    from app.plugins.workproba_cloud import storage as cloud_storage

    cloud_dir = tmp_path / "cloud"
    cloud_dir.mkdir()
    assert cloud_storage.is_managed_connector_enabled(cloud_dir, "") is False
    assert cloud_storage.is_managed_connector_enabled(cloud_dir, "  ") is False


def test_known_managed_connectors_save_and_get(tmp_path: Path) -> None:
    from app.plugins.workproba_cloud import storage as cloud_storage

    cloud_dir = tmp_path / "cloud"
    cloud_dir.mkdir()
    assert cloud_storage.get_known_managed_connectors(cloud_dir) == []

    cloud_storage.save_known_managed_connectors(
        cloud_dir,
        [
            {"id": "ihora", "name": "Ihora"},
            {"id": "", "name": "Bad"},
            {"id": "echo", "name": ""},
            {"id": "ihora", "name": "Dup"},
        ],
    )
    known = cloud_storage.get_known_managed_connectors(cloud_dir)
    assert known == [
        {"id": "ihora", "name": "Ihora"},
        {"id": "echo", "name": "echo"},
    ]


def test_build_managed_connectors_agent_prompt() -> None:
    from app.i18n import t
    from app.plugins.workproba_cloud.plugin import build_managed_connectors_agent_prompt

    text = build_managed_connectors_agent_prompt(
        "fr",
        [
            ("ihora", "Ihora", True),
            ("echo", "Echo", False),
        ],
    )
    assert t("fr", "tools.managed_connectors_header") in text
    assert "ihora" in text
    assert "Ihora" in text
    assert t("fr", "tools.managed_connectors_enabled", id="ihora", name="Ihora") in text
    assert t("fr", "tools.managed_connectors_disabled", id="echo", name="Echo") in text


def test_build_managed_connectors_agent_prompt_empty() -> None:
    from app.plugins.workproba_cloud.plugin import build_managed_connectors_agent_prompt

    assert build_managed_connectors_agent_prompt("fr", []) == ""


@pytest.mark.asyncio
async def test_invoke_managed_connector_disabled_skips_gate(
    tmp_path: Path,
) -> None:
    from pydantic_ai import RunContext
    from pydantic_ai.exceptions import ModelRetry
    from pydantic_ai.models.test import TestModel

    from app.agent.confirmation import ConfirmationGate
    from app.agent.tools import ToolContext, ToolDeps, build_agent
    from app.limits import DEFAULT_LIMITS
    from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD
    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.sandbox.runner import SandboxRunner

    from conftest import FakeProjectClient

    class FailGate(ConfirmationGate):
        async def request_effect(self, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("gate must not run when connector is disabled locally")

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    plugins_root = cloud_dir.parent
    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.test"})
    client = CloudControlPlaneClient(
        base_url="https://cloud.test",
        plugin_data_dir=cloud_dir,
    )
    client.save_tokens({"access_token": "tok", "org_id": "org-a", "device_id": "dev-1"})
    cloud_storage.set_managed_connector_enabled(cloud_dir, "echo", enabled=False)

    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s1",
            documents=[],
            plugin_data_dir=plugins_root,
            locale="fr",
            permissions_network=True,
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
        confirmation_gate=FailGate(session_id="s1", turn_id="t1"),
    )
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_WORKPROBA_CLOUD])
    tool = agent._function_toolset.tools["invoke_managed_connector"]
    ctx = RunContext(
        deps=deps,
        model=TestModel(),
        usage=None,
        prompt=None,
        tool_call_id="tc1",
    )

    with pytest.raises(ModelRetry, match="désactivé"):
        await tool.function(ctx, connector_id="echo", payload_json="{}")


def test_cloud_list_connectors_enabled_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json

    import app.auth as authmod
    from fastapi.testclient import TestClient

    import app.main as mainmod
    from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD
    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient

    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    config = {
        "base_url": "https://cloud.test",
        "tokens": {"access_token": "stub-bearer", "org_id": "org-a"},
    }
    (cloud_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")

    async def fake_list(self: CloudControlPlaneClient) -> dict:
        return {
            "connectors": [
                {"id": "ihora", "name": "Ihora", "runtime": "managed", "description": ""},
            ]
        }

    monkeypatch.setattr(CloudControlPlaneClient, "list_connectors", fake_list)

    with TestClient(mainmod.app) as test_client:
        resp = test_client.get(
            "/plugins/cloud/connectors",
            params={"plugin_data_dir": str(cloud_dir)},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["connectors"][0]["enabled"] is True

        cloud_storage.set_managed_connector_enabled(cloud_dir, "ihora", enabled=False)

        resp2 = test_client.get(
            "/plugins/cloud/connectors",
            params={"plugin_data_dir": str(cloud_dir)},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["connectors"][0]["enabled"] is False

        known = cloud_storage.get_known_managed_connectors(cloud_dir)
        assert known == [{"id": "ihora", "name": "Ihora"}]


def test_cloud_put_connector_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json

    import app.auth as authmod
    from fastapi.testclient import TestClient

    import app.main as mainmod
    from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD
    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient

    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    (cloud_dir / "config.json").write_text(
        json.dumps(
            {
                "base_url": "https://cloud.test",
                "tokens": {"access_token": "stub-bearer", "org_id": "org-a"},
            }
        ),
        encoding="utf-8",
    )

    async def fake_allowed(self: CloudControlPlaneClient) -> frozenset[str]:
        return frozenset({"ihora", "echo"})

    async def fake_list(self: CloudControlPlaneClient) -> dict:
        return {
            "connectors": [
                {"id": "ihora", "name": "Ihora", "runtime": "managed", "description": ""},
            ]
        }

    monkeypatch.setattr(
        CloudControlPlaneClient, "fetch_allowed_connector_ids", fake_allowed
    )
    monkeypatch.setattr(CloudControlPlaneClient, "list_connectors", fake_list)

    with TestClient(mainmod.app) as test_client:
        resp = test_client.put(
            "/plugins/cloud/connectors/ihora/enabled",
            json={"plugin_data_dir": str(cloud_dir), "enabled": False},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "ihora"
        assert body["enabled"] is False
        assert cloud_storage.is_managed_connector_enabled(cloud_dir, "ihora") is False

        resp2 = test_client.put(
            "/plugins/cloud/connectors/ihora/enabled",
            json={"plugin_data_dir": str(cloud_dir), "enabled": True},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["enabled"] is True
        assert cloud_storage.is_managed_connector_enabled(cloud_dir, "ihora") is True

        resp3 = test_client.put(
            "/plugins/cloud/connectors/unknown/enabled",
            json={"plugin_data_dir": str(cloud_dir), "enabled": True},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert resp3.status_code == 404
        assert "connector_not_allowed" in resp3.json()["detail"]


def test_cloud_put_connector_enabled_not_enrolled(
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
        resp = test_client.put(
            "/plugins/cloud/connectors/ihora/enabled",
            json={"plugin_data_dir": str(cloud_dir), "enabled": True},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_invoke_managed_connector_not_auth_skips_gate(
    tmp_path: Path,
) -> None:
    from pydantic_ai import RunContext
    from pydantic_ai.exceptions import ModelRetry
    from pydantic_ai.models.test import TestModel

    from app.agent.confirmation import ConfirmationGate
    from app.agent.tools import ToolContext, ToolDeps, build_agent
    from app.limits import DEFAULT_LIMITS
    from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD
    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.sandbox.runner import SandboxRunner

    from conftest import FakeProjectClient

    class FailGate(ConfirmationGate):
        async def request_effect(self, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("gate must not run when not authenticated")

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    plugins_root = cloud_dir.parent
    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.test"})

    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s1",
            documents=[],
            plugin_data_dir=plugins_root,
            locale="fr",
            permissions_network=True,
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
        confirmation_gate=FailGate(session_id="s1", turn_id="t1"),
    )
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_WORKPROBA_CLOUD])
    tool = agent._function_toolset.tools["invoke_managed_connector"]
    ctx = RunContext(
        deps=deps,
        model=TestModel(),
        usage=None,
        prompt=None,
        tool_call_id="tc-auth",
    )

    with pytest.raises(ModelRetry, match="authentifi"):
        await tool.function(ctx, connector_id="ihora", payload_json="{}")
