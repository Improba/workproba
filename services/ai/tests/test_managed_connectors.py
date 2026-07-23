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
            {
                "id": "ihora",
                "name": "Ihora",
                "tools": [
                    {
                        "name": "list_absences",
                        "action": "list_absences",
                        "description": "List absences",
                        "input_schema": {"type": "object", "properties": {}},
                    }
                ],
            },
            {"id": "", "name": "Bad"},
            {"id": "echo", "name": ""},
            {"id": "ihora", "name": "Dup"},
        ],
    )
    known = cloud_storage.get_known_managed_connectors(cloud_dir)
    assert known == [
        {
            "id": "ihora",
            "name": "Ihora",
            "tools": [
                {
                    "name": "list_absences",
                    "action": "list_absences",
                    "description": "List absences",
                    "input_schema": {"type": "object", "properties": {}},
                }
            ],
        },
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
    assert t("fr", "tools.managed_connectors_ihora_users_hint") in text
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
        assert known == [{"id": "ihora", "name": "Ihora", "tools": []}]


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
    _seed_ihora_connectors_cache(cloud_dir)

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


IHORA_TOOLS = [
    {
        "name": "list_absences",
        "action": "list_absences",
        "description": "Lister les absences d un collaborateur sur une periode",
        "effect": "read",
        "visibility": "guided",
        "input_schema": {
            "type": "object",
            "properties": {
                "employeeId": {"type": ["string", "number"]},
                "email": {"type": "string"},
                "from": {"type": "string"},
                "to": {"type": "string"},
            },
            "required": ["from", "to"],
            "anyOf": [
                {"required": ["employeeId"]},
                {"required": ["email"]},
            ],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_timesheet",
        "action": "get_timesheet",
        "description": "Recuperer le timesheet d un collaborateur sur une periode",
        "effect": "read",
        "visibility": "guided",
        "input_schema": {
            "type": "object",
            "properties": {
                "employeeId": {"type": ["string", "number"]},
                "email": {"type": "string"},
                "from": {"type": "string"},
                "to": {"type": "string"},
            },
            "required": ["from", "to"],
            "anyOf": [
                {"required": ["employeeId"]},
                {"required": ["email"]},
            ],
            "additionalProperties": False,
        },
    },
    {
        "name": "create_timesheet",
        "action": "create_timesheet",
        "description": "Creer une saisie de temps",
        "effect": "write",
        "visibility": "standard",
        "input_schema": {
            "type": "object",
            "properties": {
                "employeeId": {"type": ["string", "number"]},
                "email": {"type": "string"},
                "date": {"type": "string"},
                "hours": {"type": "number", "minimum": 0, "maximum": 24},
                "project": {"type": "string"},
                "projectId": {"type": ["string", "number"]},
                "description": {"type": "string"},
            },
            "required": ["date", "hours"],
            "anyOf": [
                {"required": ["employeeId"]},
                {"required": ["email"]},
            ],
            "additionalProperties": False,
        },
    },
]


def _seed_ihora_connectors_cache(cloud_dir: Path) -> None:
    from app.plugins.workproba_cloud import storage as cloud_storage

    cloud_storage.save_known_managed_connectors(
        cloud_dir,
        [
            {
                "id": "ihora",
                "name": "Ihora",
                "tools": IHORA_TOOLS,
            }
        ],
    )


def test_managed_tool_name_uses_lossless_format() -> None:
    from app.plugins.workproba_cloud.plugin import (
        managed_tool_name,
        parse_managed_tool_name,
    )

    assert managed_tool_name("ihora", "list_absences") == "managed__ihora__list_absences"
    assert (
        managed_tool_name("ihora.shaped", "get_timesheet")
        == "managed__ihora.shaped__get_timesheet"
    )
    assert parse_managed_tool_name("managed__ihora.shaped__get_timesheet") == (
        "ihora.shaped",
        "get_timesheet",
    )


def test_normalize_tool_input_schema_defaults_additional_properties_false() -> None:
    from app.plugins.workproba_cloud.plugin import normalize_tool_input_schema

    assert normalize_tool_input_schema(None) == {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }
    assert normalize_tool_input_schema({"type": "object", "properties": {"x": {"type": "string"}}}) == {
        "type": "object",
        "properties": {"x": {"type": "string"}},
        "additionalProperties": False,
    }
    assert normalize_tool_input_schema(
        {"type": "object", "properties": {}, "additionalProperties": True}
    ) == {
        "type": "object",
        "properties": {},
        "additionalProperties": True,
    }


@pytest.mark.asyncio
async def test_invoke_managed_connector_locked_refuses_standard_only_connector(
    tmp_path: Path,
) -> None:
    from pydantic_ai import RunContext
    from pydantic_ai.exceptions import ModelRetry
    from pydantic_ai.models.test import TestModel

    from app.agent.tools import ToolContext, ToolDeps, build_agent
    from app.limits import DEFAULT_LIMITS
    from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD
    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.sandbox.runner import SandboxRunner

    from conftest import FakeProjectClient

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    plugins_root = cloud_dir.parent
    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.test"})
    cloud_storage.set_managed_connector_enabled(cloud_dir, "echo", enabled=True)
    cloud_storage.save_known_managed_connectors(
        cloud_dir,
        [
            {
                "id": "echo",
                "name": "Echo",
                "tools": [
                    {
                        "name": "echo",
                        "action": "echo",
                        "visibility": "standard",
                        "input_schema": {"type": "object", "properties": {}},
                    }
                ],
            }
        ],
    )

    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s1",
            documents=[],
            plugin_data_dir=plugins_root,
            locale="fr",
            permissions_network=True,
            ui_mode="locked",
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
        confirmation_gate=None,
    )
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_WORKPROBA_CLOUD])
    tool = agent._function_toolset.tools["invoke_managed_connector"]
    ctx = RunContext(
        deps=deps,
        model=TestModel(),
        usage=None,
        prompt=None,
        tool_call_id="tc-guided-echo",
    )

    with pytest.raises(ModelRetry, match="réglages verrouillés"):
        await tool.function(ctx, connector_id="echo", payload_json="{}")


def test_classify_managed_tool_is_external_send() -> None:
    proposal = classify_effect(
        "managed__ihora__list_absences",
        {},
        permissions_network=True,
    )
    assert proposal is not None
    assert proposal.effect == "external_send"
    assert proposal.targets == ["ihora"]


def test_build_agent_registers_managed_ihora_tool(tmp_path: Path) -> None:
    from pydantic_ai.models.test import TestModel

    from app.agent.tools import build_agent
    from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    _seed_ihora_connectors_cache(cloud_dir)

    agent = build_agent(
        TestModel(),
        active_plugins=[PLUGIN_WORKPROBA_CLOUD],
        plugin_data_dir=cloud_dir.parent,
    )
    assert "managed__ihora__list_absences" in agent._function_toolset.tools
    assert "invoke_managed_connector" in agent._function_toolset.tools


def test_build_agent_skips_disabled_managed_tool(tmp_path: Path) -> None:
    from pydantic_ai.models.test import TestModel

    from app.agent.tools import build_agent
    from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD
    from app.plugins.workproba_cloud import storage as cloud_storage

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    _seed_ihora_connectors_cache(cloud_dir)
    cloud_storage.set_managed_connector_enabled(cloud_dir, "ihora", enabled=False)

    agent = build_agent(
        TestModel(),
        active_plugins=[PLUGIN_WORKPROBA_CLOUD],
        plugin_data_dir=cloud_dir.parent,
    )
    assert "managed__ihora__list_absences" not in agent._function_toolset.tools


def test_build_agent_agent_registers_standard_managed_tools(tmp_path: Path) -> None:
    from pydantic_ai.models.test import TestModel

    from app.agent.tools import build_agent
    from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    _seed_ihora_connectors_cache(cloud_dir)

    agent = build_agent(
        TestModel(),
        active_plugins=[PLUGIN_WORKPROBA_CLOUD],
        plugin_data_dir=cloud_dir.parent,
        ui_mode="agent",
    )
    assert "managed__ihora__list_absences" in agent._function_toolset.tools
    assert "managed__ihora__get_timesheet" in agent._function_toolset.tools
    assert "managed__ihora__create_timesheet" in agent._function_toolset.tools


@pytest.mark.asyncio
async def test_managed_tool_shim_builds_payload_with_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic_ai import RunContext
    from pydantic_ai.models.test import TestModel

    from app.agent.tools import ToolContext, ToolDeps, build_agent
    from app.limits import DEFAULT_LIMITS
    from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD
    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.sandbox.runner import SandboxRunner

    from conftest import FakeProjectClient

    captured: dict[str, Any] = {}

    async def fake_impl(ctx, *, connector_id, payload, gate_tool_name, **kwargs):
        captured["connector_id"] = connector_id
        captured["payload"] = payload
        captured["gate_tool_name"] = gate_tool_name
        return {"ok": True, "human_summary": "done"}

    monkeypatch.setattr(
        "app.plugins.workproba_cloud.plugin.invoke_managed_connector_impl",
        fake_impl,
    )

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    plugins_root = cloud_dir.parent
    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.test"})
    client = CloudControlPlaneClient(
        base_url="https://cloud.test",
        plugin_data_dir=cloud_dir,
    )
    client.save_tokens({"access_token": "tok", "org_id": "org-a", "device_id": "dev-1"})
    _seed_ihora_connectors_cache(cloud_dir)

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
        confirmation_gate=None,
    )
    agent = build_agent(
        TestModel(),
        active_plugins=[PLUGIN_WORKPROBA_CLOUD],
        plugin_data_dir=plugins_root,
    )
    tool = agent._function_toolset.tools["managed__ihora__list_absences"]
    ctx = RunContext(
        deps=deps,
        model=TestModel(),
        usage=None,
        prompt=None,
        tool_call_id="tc-managed",
    )

    await tool.function(ctx, **{"from": "2026-01-01"})
    assert captured["connector_id"] == "ihora"
    assert captured["payload"] == {"action": "list_absences", "from": "2026-01-01"}
    assert captured["gate_tool_name"] == "managed__ihora__list_absences"


def test_cloud_list_connectors_returns_tools(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
                    "id": "ihora",
                    "name": "Ihora",
                    "runtime": "managed",
                    "description": "",
                    "tools": IHORA_TOOLS,
                },
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
        assert len(body["connectors"][0]["tools"]) == 3
        assert body["connectors"][0]["tools"][0]["name"] == "list_absences"


def test_build_agent_locked_hides_standard_managed_tool(tmp_path: Path) -> None:
    from pydantic_ai.models.test import TestModel

    from app.agent.tools import build_agent
    from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    _seed_ihora_connectors_cache(cloud_dir)

    agent = build_agent(
        TestModel(),
        active_plugins=[PLUGIN_WORKPROBA_CLOUD],
        plugin_data_dir=cloud_dir.parent,
        ui_mode="locked",
    )
    assert "managed__ihora__list_absences" in agent._function_toolset.tools
    assert "managed__ihora__create_timesheet" not in agent._function_toolset.tools


@pytest.mark.asyncio
async def test_invoke_managed_connector_locked_refuses_standard_action(
    tmp_path: Path,
) -> None:
    from pydantic_ai import RunContext
    from pydantic_ai.exceptions import ModelRetry
    from pydantic_ai.models.test import TestModel

    from app.agent.tools import ToolContext, ToolDeps, build_agent
    from app.limits import DEFAULT_LIMITS
    from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD
    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.sandbox.runner import SandboxRunner

    from conftest import FakeProjectClient

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    plugins_root = cloud_dir.parent
    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.test"})
    cloud_storage.set_managed_connector_enabled(cloud_dir, "ihora", enabled=True)
    _seed_ihora_connectors_cache(cloud_dir)
    client = CloudControlPlaneClient(
        base_url="https://cloud.test",
        plugin_data_dir=cloud_dir,
    )
    client.save_tokens({"access_token": "tok", "org_id": "org-a", "device_id": "dev-1"})

    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s1",
            documents=[],
            plugin_data_dir=plugins_root,
            locale="fr",
            permissions_network=True,
            ui_mode="locked",
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
        confirmation_gate=None,
    )
    agent = build_agent(
        TestModel(),
        active_plugins=[PLUGIN_WORKPROBA_CLOUD],
        plugin_data_dir=plugins_root,
        ui_mode="locked",
    )
    tool = agent._function_toolset.tools["invoke_managed_connector"]
    ctx = RunContext(
        deps=deps,
        model=TestModel(),
        usage=None,
        prompt=None,
        tool_call_id="tc-guided-create",
    )

    with pytest.raises(ModelRetry, match="réglages verrouillés"):
        await tool.function(
            ctx,
            connector_id="ihora",
            payload_json='{"action":"create_timesheet","date":"2026-07-03","hours":8,"employeeId":1}',
        )


@pytest.mark.asyncio
async def test_refresh_known_managed_connectors_cache_clears_tools(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD
    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient
    from app.plugins.workproba_cloud.plugin import refresh_known_managed_connectors_cache
    from app.plugins.workproba_cloud.sync_service import is_cloud_enrolled

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.test"})
    _seed_ihora_connectors_cache(cloud_dir)
    assert cloud_storage.get_known_managed_connectors(cloud_dir)[0]["tools"]

    async def fake_list(self: CloudControlPlaneClient) -> dict:
        return {"connectors": []}

    monkeypatch.setattr(CloudControlPlaneClient, "list_connectors", fake_list)
    monkeypatch.setattr(
        "app.plugins.workproba_cloud.plugin.is_cloud_enrolled",
        lambda _cloud_dir: True,
    )

    await refresh_known_managed_connectors_cache(cloud_dir)
    assert cloud_storage.get_known_managed_connectors(cloud_dir) == []


def test_extract_catalog_version_accepts_camel_and_snake() -> None:
    assert (
        CloudControlPlaneClient.extract_catalog_version(
            {"catalogVersion": "2026.07.23.1", "connectors": []}
        )
        == "2026.07.23.1"
    )
    assert (
        CloudControlPlaneClient.extract_catalog_version(
            {"catalog_version": "2026.07.23.2", "connectors": []}
        )
        == "2026.07.23.2"
    )
    assert CloudControlPlaneClient.extract_catalog_version({"connectors": []}) is None


def test_known_managed_connectors_catalog_version_roundtrip(tmp_path: Path) -> None:
    from app.plugins.workproba_cloud import storage as cloud_storage

    cloud_dir = tmp_path / "cloud"
    cloud_dir.mkdir()
    assert cloud_storage.get_known_managed_connectors_catalog_version(cloud_dir) is None

    cloud_storage.save_known_managed_connectors(
        cloud_dir,
        [{"id": "echo", "name": "Echo"}],
        catalog_version="2026.07.23.1",
    )
    assert (
        cloud_storage.get_known_managed_connectors_catalog_version(cloud_dir)
        == "2026.07.23.1"
    )


@pytest.mark.asyncio
async def test_refresh_known_managed_connectors_cache_skips_save_same_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD
    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient
    from app.plugins.workproba_cloud.plugin import refresh_known_managed_connectors_cache

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.test"})
    cloud_storage.save_known_managed_connectors(
        cloud_dir,
        [{"id": "ihora", "name": "Ihora", "tools": IHORA_TOOLS}],
        catalog_version="2026.07.23.1",
    )
    config_mtime_before = (cloud_dir / "config.json").stat().st_mtime

    async def fake_list(self: CloudControlPlaneClient) -> dict:
        return {
            "connectors": [{"id": "echo", "name": "Echo"}],
            "catalogVersion": "2026.07.23.1",
        }

    save_called = {"value": False}
    original_save = cloud_storage.save_known_managed_connectors

    def tracking_save(*args, **kwargs):
        save_called["value"] = True
        return original_save(*args, **kwargs)

    monkeypatch.setattr(CloudControlPlaneClient, "list_connectors", fake_list)
    monkeypatch.setattr(
        "app.plugins.workproba_cloud.plugin.is_cloud_enrolled",
        lambda _cloud_dir: True,
    )
    monkeypatch.setattr(cloud_storage, "save_known_managed_connectors", tracking_save)

    allowed = await refresh_known_managed_connectors_cache(cloud_dir)

    assert allowed == frozenset({"echo"})
    assert save_called["value"] is False
    assert cloud_storage.get_known_managed_connectors(cloud_dir)[0]["id"] == "ihora"
    assert (
        cloud_storage.get_known_managed_connectors_catalog_version(cloud_dir)
        == "2026.07.23.1"
    )
    assert (cloud_dir / "config.json").stat().st_mtime == config_mtime_before


@pytest.mark.asyncio
async def test_refresh_known_managed_connectors_cache_refreshes_on_version_bump(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD
    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient
    from app.plugins.workproba_cloud.plugin import refresh_known_managed_connectors_cache

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.test"})
    cloud_storage.save_known_managed_connectors(
        cloud_dir,
        [{"id": "ihora", "name": "Ihora", "tools": IHORA_TOOLS}],
        catalog_version="2026.07.23.1",
    )

    async def fake_list(self: CloudControlPlaneClient) -> dict:
        return {
            "connectors": [
                {
                    "id": "echo",
                    "name": "Echo",
                    "tools": [
                        {
                            "name": "ping",
                            "action": "ping",
                            "effect": "read",
                        }
                    ],
                }
            ],
            "catalog_version": "2026.07.23.2",
        }

    monkeypatch.setattr(CloudControlPlaneClient, "list_connectors", fake_list)
    monkeypatch.setattr(
        "app.plugins.workproba_cloud.plugin.is_cloud_enrolled",
        lambda _cloud_dir: True,
    )

    allowed = await refresh_known_managed_connectors_cache(cloud_dir)

    assert allowed == frozenset({"echo"})
    known = cloud_storage.get_known_managed_connectors(cloud_dir)
    assert known == [
        {
            "id": "echo",
            "name": "Echo",
            "tools": [{"name": "ping", "action": "ping", "effect": "read"}],
        }
    ]
    assert (
        cloud_storage.get_known_managed_connectors_catalog_version(cloud_dir)
        == "2026.07.23.2"
    )


@pytest.mark.asyncio
async def test_invoke_managed_connector_validates_payload_before_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic_ai import RunContext
    from pydantic_ai.exceptions import ModelRetry
    from pydantic_ai.models.test import TestModel

    from app.agent.confirmation import ConfirmationGate
    from app.agent.tools import ToolContext, ToolDeps, build_agent
    from app.limits import DEFAULT_LIMITS
    from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD
    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient
    from app.sandbox.runner import SandboxRunner

    from conftest import FakeProjectClient

    class ExplodingGate(ConfirmationGate):
        async def request_effect(self, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("gate must not run on invalid payload")

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    plugins_root = cloud_dir.parent
    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.test"})
    cloud_storage.set_managed_connector_enabled(cloud_dir, "ihora", enabled=True)
    _seed_ihora_connectors_cache(cloud_dir)
    client = CloudControlPlaneClient(
        base_url="https://cloud.test",
        plugin_data_dir=cloud_dir,
    )
    client.save_tokens({"access_token": "tok", "org_id": "org-a", "device_id": "dev-1"})

    async def fake_allowed(self: CloudControlPlaneClient) -> set[str]:
        return {"ihora"}

    monkeypatch.setattr(CloudControlPlaneClient, "fetch_allowed_connector_ids", fake_allowed)

    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s1",
            documents=[],
            plugin_data_dir=plugins_root,
            locale="fr",
            permissions_network=True,
            ui_mode="agent",
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
        confirmation_gate=ExplodingGate(session_id="s1", turn_id="t1"),
    )
    agent = build_agent(
        TestModel(),
        active_plugins=[PLUGIN_WORKPROBA_CLOUD],
        plugin_data_dir=plugins_root,
        ui_mode="agent",
    )
    tool = agent._function_toolset.tools["invoke_managed_connector"]
    ctx = RunContext(
        deps=deps,
        model=TestModel(),
        usage=None,
        prompt=None,
        tool_call_id="tc-invalid-payload",
    )

    with pytest.raises(ModelRetry, match="Paramètres invalides"):
        await tool.function(
            ctx,
            connector_id="ihora",
            payload_json='{"action":"create_timesheet","date":"2026-07-03"}',
        )


def test_is_managed_read_action_from_cached_effect(tmp_path: Path) -> None:
    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.plugins.workproba_cloud.plugin import _is_managed_read_action

    cloud_dir = tmp_path / "cloud"
    cloud_dir.mkdir()
    _seed_ihora_connectors_cache(cloud_dir)

    assert _is_managed_read_action(cloud_dir, "ihora", "list_absences") is True
    assert _is_managed_read_action(cloud_dir, "ihora", "get_timesheet") is True
    assert _is_managed_read_action(cloud_dir, "ihora", "create_timesheet") is False
    assert _is_managed_read_action(cloud_dir, "ihora", "unknown_action") is False
    assert _is_managed_read_action(cloud_dir, "ihora", None) is False

    cloud_storage.save_known_managed_connectors(
        cloud_dir,
        [
            {
                "id": "ihora",
                "name": "Ihora",
                "tools": [
                    {
                        "name": "list_users",
                        "action": "list_users",
                        "description": "List users",
                        "input_schema": {"type": "object", "properties": {}},
                    }
                ],
            }
        ],
    )
    assert _is_managed_read_action(cloud_dir, "ihora", "list_users") is False


def test_find_cached_tool_matches_action_not_name(tmp_path: Path) -> None:
    """name≠action : ne pas résoudre par name (aligné sur le cloud)."""
    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.plugins.workproba_cloud.plugin import (
        _find_cached_tool,
        _is_managed_read_action,
    )

    cloud_dir = tmp_path / "cloud"
    cloud_dir.mkdir()
    cloud_storage.save_known_managed_connectors(
        cloud_dir,
        [
            {
                "id": "ihora",
                "name": "Ihora",
                "tools": [
                    {
                        "name": "list_users",
                        "action": "update_project_member",
                        "effect": "write",
                        "description": "Write disguised",
                        "input_schema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "other",
                        "action": "list_users",
                        "effect": "read",
                        "description": "Real list",
                        "input_schema": {"type": "object", "properties": {}},
                    },
                ],
            }
        ],
    )
    # Resolve by action only
    found = _find_cached_tool(cloud_dir, "ihora", "list_users")
    assert found is not None
    assert found["effect"] == "read"
    assert found["action"] == "list_users"
    # Looking up by name must NOT find the write tool as a read
    assert _is_managed_read_action(cloud_dir, "ihora", "list_users") is True
    assert _find_cached_tool(cloud_dir, "ihora", "update_project_member") is not None
    assert (
        _is_managed_read_action(cloud_dir, "ihora", "update_project_member") is False
    )


@pytest.mark.asyncio
async def test_read_managed_tool_skips_confirmation_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic_ai import RunContext
    from pydantic_ai.models.test import TestModel

    from app.agent.confirmation import ConfirmationGate
    from app.agent.tools import ToolContext, ToolDeps, build_agent
    from app.limits import DEFAULT_LIMITS
    from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD
    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient
    from app.sandbox.runner import SandboxRunner

    from conftest import FakeProjectClient

    class FailGate(ConfirmationGate):
        async def request_effect(self, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("gate must not run for read managed tools")

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    plugins_root = cloud_dir.parent
    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.test"})
    cloud_storage.set_managed_connector_enabled(cloud_dir, "ihora", enabled=True)
    _seed_ihora_connectors_cache(cloud_dir)
    client = CloudControlPlaneClient(
        base_url="https://cloud.test",
        plugin_data_dir=cloud_dir,
    )
    client.save_tokens({"access_token": "tok", "org_id": "org-a", "device_id": "dev-1"})

    async def fake_allowed(self: CloudControlPlaneClient) -> set[str]:
        return {"ihora"}

    async def fake_invoke_remote(self, connector_id, payload, identity):  # type: ignore[no-untyped-def]
        return {
            "ok": True,
            "result": {"action": "list_absences", "absences": []},
        }

    monkeypatch.setattr(CloudControlPlaneClient, "fetch_allowed_connector_ids", fake_allowed)
    monkeypatch.setattr(
        "app.plugins.workproba_cloud.plugin.open_remote_capability_gateway",
        lambda **kwargs: type("GW", (), {"invoke_remote": fake_invoke_remote})(),
    )

    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s1",
            documents=[],
            plugin_data_dir=plugins_root,
            locale="fr",
            permissions_network=True,
            managed_allowed_connector_ids=frozenset({"ihora"}),
            audit_enabled=True,
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
        confirmation_gate=FailGate(session_id="s1", turn_id="t1"),
    )
    agent = build_agent(
        TestModel(),
        active_plugins=[PLUGIN_WORKPROBA_CLOUD],
        plugin_data_dir=plugins_root,
    )
    tool = agent._function_toolset.tools["managed__ihora__list_absences"]
    ctx = RunContext(
        deps=deps,
        model=TestModel(),
        usage=None,
        prompt=None,
        tool_call_id="tc-read-skip-gate",
    )

    result = await tool.function(
        ctx,
        **{"from": "2026-01-01", "to": "2026-01-31", "email": "user@example.com"},
    )
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_write_managed_tool_calls_confirmation_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic_ai import RunContext
    from pydantic_ai.models.test import TestModel

    from app.agent.confirmation import ConfirmationGate
    from app.agent.tools import ToolContext, ToolDeps, build_agent
    from app.limits import DEFAULT_LIMITS
    from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD
    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient
    from app.sandbox.runner import SandboxRunner

    from conftest import FakeProjectClient

    gate_called = {"value": False}

    class CaptureGate(ConfirmationGate):
        async def request_effect(self, **kwargs):  # type: ignore[no-untyped-def]
            gate_called["value"] = True
            return "approved"

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    plugins_root = cloud_dir.parent
    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.test"})
    cloud_storage.set_managed_connector_enabled(cloud_dir, "ihora", enabled=True)
    _seed_ihora_connectors_cache(cloud_dir)
    client = CloudControlPlaneClient(
        base_url="https://cloud.test",
        plugin_data_dir=cloud_dir,
    )
    client.save_tokens({"access_token": "tok", "org_id": "org-a", "device_id": "dev-1"})

    async def fake_allowed(self: CloudControlPlaneClient) -> set[str]:
        return {"ihora"}

    async def fake_invoke_remote(self, connector_id, payload, identity):  # type: ignore[no-untyped-def]
        return {"ok": True, "result": {"action": "create_timesheet"}}

    monkeypatch.setattr(CloudControlPlaneClient, "fetch_allowed_connector_ids", fake_allowed)
    monkeypatch.setattr(
        "app.plugins.workproba_cloud.plugin.open_remote_capability_gateway",
        lambda **kwargs: type("GW", (), {"invoke_remote": fake_invoke_remote})(),
    )

    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s1",
            documents=[],
            plugin_data_dir=plugins_root,
            locale="fr",
            permissions_network=True,
            managed_allowed_connector_ids=frozenset({"ihora"}),
            ui_mode="agent",
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
        confirmation_gate=CaptureGate(session_id="s1", turn_id="t1"),
    )
    agent = build_agent(
        TestModel(),
        active_plugins=[PLUGIN_WORKPROBA_CLOUD],
        plugin_data_dir=plugins_root,
        ui_mode="agent",
    )
    tool = agent._function_toolset.tools["managed__ihora__create_timesheet"]
    ctx = RunContext(
        deps=deps,
        model=TestModel(),
        usage=None,
        prompt=None,
        tool_call_id="tc-write-gate",
    )

    await tool.function(
        ctx,
        date="2026-07-03",
        hours=8,
        employeeId=1,
    )
    assert gate_called["value"] is True


@pytest.mark.asyncio
async def test_invoke_generic_unknown_action_calls_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic_ai import RunContext
    from pydantic_ai.models.test import TestModel

    from app.agent.confirmation import ConfirmationGate
    from app.agent.tools import ToolContext, ToolDeps, build_agent
    from app.limits import DEFAULT_LIMITS
    from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD
    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient
    from app.sandbox.runner import SandboxRunner

    from conftest import FakeProjectClient

    gate_called = {"value": False}

    class CaptureGate(ConfirmationGate):
        async def request_effect(self, **kwargs):  # type: ignore[no-untyped-def]
            gate_called["value"] = True
            return "approved"

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    plugins_root = cloud_dir.parent
    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.test"})
    cloud_storage.set_managed_connector_enabled(cloud_dir, "ihora", enabled=True)
    _seed_ihora_connectors_cache(cloud_dir)
    client = CloudControlPlaneClient(
        base_url="https://cloud.test",
        plugin_data_dir=cloud_dir,
    )
    client.save_tokens({"access_token": "tok", "org_id": "org-a", "device_id": "dev-1"})

    async def fake_allowed(self: CloudControlPlaneClient) -> set[str]:
        return {"ihora"}

    async def fake_invoke_remote(self, connector_id, payload, identity):  # type: ignore[no-untyped-def]
        return {"ok": True, "result": {"action": "unknown_action"}}

    monkeypatch.setattr(CloudControlPlaneClient, "fetch_allowed_connector_ids", fake_allowed)
    monkeypatch.setattr(
        "app.plugins.workproba_cloud.plugin.open_remote_capability_gateway",
        lambda **kwargs: type("GW", (), {"invoke_remote": fake_invoke_remote})(),
    )

    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s1",
            documents=[],
            plugin_data_dir=plugins_root,
            locale="fr",
            permissions_network=True,
            managed_allowed_connector_ids=frozenset({"ihora"}),
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
        confirmation_gate=CaptureGate(session_id="s1", turn_id="t1"),
    )
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_WORKPROBA_CLOUD])
    tool = agent._function_toolset.tools["invoke_managed_connector"]
    ctx = RunContext(
        deps=deps,
        model=TestModel(),
        usage=None,
        prompt=None,
        tool_call_id="tc-unknown-gate",
    )

    await tool.function(
        ctx,
        connector_id="ihora",
        payload_json='{"action":"unknown_action"}',
    )
    assert gate_called["value"] is True
