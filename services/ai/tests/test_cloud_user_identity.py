"""Tests identité utilisateur cloud (login, prompt agent, pré-résolution Ihora)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.models.test import TestModel

import app.auth as authmod
import app.main as mainmod
from app.agent.confirmation import ConfirmationGate
from app.agent.tools import ToolContext, ToolDeps, build_agent
from app.limits import DEFAULT_LIMITS
from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD
from app.plugins.workproba_cloud import storage as cloud_storage
from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient
from app.plugins.workproba_cloud.plugin import (
    LIST_USERS_PRERESOLVE_TIMEOUT_SECONDS,
    _match_ihora_listed_users,
    _preresolve_ihora_user_for_gate,
    invoke_managed_connector_impl,
)
from app.plugins.ports.remote_capability_gateway import DEFAULT_REMOTE_TIMEOUT_SECONDS
from app.sandbox.runner import SandboxRunner

from conftest import FakeProjectClient

INTERNAL_HEADERS = {"X-Internal-Secret": "desktop-dev-secret"}


@pytest.fixture(autouse=True)
def _patch_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)


def test_save_and_get_current_user_identity(tmp_path: Path) -> None:
    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)

    saved = cloud_storage.save_current_user_identity(
        cloud_dir,
        username="sylvain.meylan@improba.ch",
    )
    assert saved["username"] == "sylvain.meylan@improba.ch"
    assert saved["email"] == "sylvain.meylan@improba.ch"

    loaded = cloud_storage.get_current_user_identity(cloud_dir)
    assert loaded is not None
    assert loaded["email"] == "sylvain.meylan@improba.ch"


def test_clear_enrollment_removes_identity(tmp_path: Path) -> None:
    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    cloud_storage.save_config(
        cloud_dir,
        {
            "base_url": "https://cloud.example.test",
            "tokens": {"access_token": "tok"},
            "current_user_identity": {"username": "alice@org.test"},
        },
    )

    cloud_storage.clear_enrollment(cloud_dir)

    assert cloud_storage.get_current_user_identity(cloud_dir) is None
    assert cloud_storage.get_access_token(cloud_dir) is None


def test_cloud_status_exposes_current_user_email(tmp_path: Path) -> None:
    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    cloud_storage.save_config(
        cloud_dir,
        {
            "base_url": "https://cloud.example.test",
            "tokens": {"access_token": "tok"},
        },
    )
    cloud_storage.save_current_user_identity(
        cloud_dir,
        username="bob@example.com",
    )

    with TestClient(mainmod.app) as client:
        resp = client.get(
            "/plugins/cloud/status",
            params={"plugin_data_dir": str(cloud_dir)},
            headers=INTERNAL_HEADERS,
        )
    assert resp.status_code == 200
    assert resp.json()["current_user_email"] == "bob@example.com"


def test_cloud_enroll_persists_username(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)

    async def fake_authenticate(self, **kwargs):  # type: ignore[no-untyped-def]
        self.save_tokens({"access_token": "tok", "org_id": "org-1"})
        return {"authenticated": True, "method": "bearer"}

    monkeypatch.setattr(CloudControlPlaneClient, "authenticate", fake_authenticate)

    with TestClient(mainmod.app) as client:
        resp = client.post(
            "/plugins/cloud/enroll",
            json={
                "plugin_data_dir": str(cloud_dir),
                "base_url": "https://cloud.example.test",
                "bearer_token": "user-jwt",
                "username": "sylvain.meylan@improba.ch",
            },
            headers=INTERNAL_HEADERS,
        )
    assert resp.status_code == 200
    identity = cloud_storage.get_current_user_identity(cloud_dir)
    assert identity is not None
    assert identity["username"] == "sylvain.meylan@improba.ch"
    assert identity["email"] == "sylvain.meylan@improba.ch"


def test_match_ihora_listed_users_single_fragment_match() -> None:
    users = [
        {
            "userId": 7,
            "email": "sylvain.meylan@improba.ch",
            "firstname": "Sylvain",
            "lastname": "Meylan",
        }
    ]
    matches = _match_ihora_listed_users(users, "sylvain.meylan")
    assert len(matches) == 1
    assert matches[0]["userId"] == 7


def test_build_agent_includes_cloud_identity_prompt(tmp_path: Path) -> None:
    from pydantic_ai.models.test import TestModel

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.test"})
    cloud_storage.save_current_user_identity(
        cloud_dir,
        username="sylvain.meylan@improba.ch",
        display_name="Sylvain Meylan",
    )
    client = CloudControlPlaneClient(
        base_url="https://cloud.test",
        plugin_data_dir=cloud_dir,
    )
    client.save_tokens({"access_token": "tok", "org_id": "org-a"})

    agent = build_agent(
        TestModel(),
        active_plugins=[PLUGIN_WORKPROBA_CLOUD],
        plugin_data_dir=cloud_dir.parent,
    )
    prompt_fn = None
    for runner in agent._system_prompt_functions:
        if runner.function.__name__ == "cloud_current_user_identity_prompt":
            prompt_fn = runner.function
            break
    assert prompt_fn is not None

    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s1",
            documents=[],
            plugin_data_dir=cloud_dir.parent,
            locale="fr",
            current_user_email="sylvain.meylan@improba.ch",
            current_user_display_name="Sylvain Meylan",
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
    )
    ctx = RunContext(deps=deps, model=TestModel(), usage=None, prompt=None)

    import asyncio

    rendered = asyncio.run(prompt_fn(ctx))
    assert "sylvain.meylan@improba.ch" in rendered
    assert "ajoute-moi" in rendered.lower()


def test_build_agent_identity_prompt_username_only_without_add_me_hint(
    tmp_path: Path,
) -> None:
    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.test"})
    cloud_storage.save_current_user_identity(
        cloud_dir,
        username="sylvain.meylan",
        display_name="Sylvain Meylan",
    )

    agent = build_agent(
        TestModel(),
        active_plugins=[PLUGIN_WORKPROBA_CLOUD],
        plugin_data_dir=cloud_dir.parent,
    )
    prompt_fn = None
    for runner in agent._system_prompt_functions:
        if runner.function.__name__ == "cloud_current_user_identity_prompt":
            prompt_fn = runner.function
            break
    assert prompt_fn is not None

    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s1",
            documents=[],
            plugin_data_dir=cloud_dir.parent,
            locale="fr",
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
    )
    ctx = RunContext(deps=deps, model=TestModel(), usage=None, prompt=None)

    import asyncio

    rendered = asyncio.run(prompt_fn(ctx))
    assert "sylvain.meylan" in rendered
    assert "list_users" in rendered
    assert "ajoute-moi" not in rendered.lower()


@pytest.mark.asyncio
async def test_preresolve_numeric_user_id_email_conflict_raises(
    tmp_path: Path,
) -> None:
    from pydantic_ai.exceptions import ModelRetry

    payload = {
        "action": "update_project_member",
        "projectId": 42,
        "userId": 1,
        "email": "sylvain.meylan@improba.ch",
    }

    class FakeGateway:
        async def invoke_remote(self, connector_id, list_payload, identity):  # type: ignore[no-untyped-def]
            return {
                "ok": True,
                "result": {
                    "users": [
                        {
                            "userId": 7,
                            "email": "sylvain.meylan@improba.ch",
                            "firstname": "Sylvain",
                            "lastname": "Meylan",
                        }
                    ],
                    "action": "list_users",
                },
            }

    identity = type("Identity", (), {})()
    with pytest.raises(ModelRetry, match="Conflit d'identité|userId 1"):
        await _preresolve_ihora_user_for_gate(
            FakeGateway(),
            connector_id="ihora",
            payload=payload,
            identity=identity,
            locale="fr",
        )
    assert payload["userId"] == 1


@pytest.mark.asyncio
async def test_preresolve_email_only_mutates_payload_user_id(tmp_path: Path) -> None:
    payload = {
        "action": "update_project_member",
        "projectId": 42,
        "email": "sylvain.meylan@improba.ch",
    }

    class FakeGateway:
        async def invoke_remote(self, connector_id, list_payload, identity):  # type: ignore[no-untyped-def]
            return {
                "ok": True,
                "result": {
                    "users": [
                        {
                            "userId": 7,
                            "email": "sylvain.meylan@improba.ch",
                            "firstname": "Sylvain",
                            "lastname": "Meylan",
                        }
                    ],
                    "action": "list_users",
                },
            }

    identity = type("Identity", (), {})()
    resolved, failed = await _preresolve_ihora_user_for_gate(
        FakeGateway(),
        connector_id="ihora",
        payload=payload,
        identity=identity,
        locale="fr",
    )
    assert failed is False
    assert resolved is not None
    assert payload["userId"] == 7


@pytest.mark.asyncio
async def test_mandatory_user_resolution_failure_raises_before_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    plugins_root = cloud_dir.parent
    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.test"})
    cloud_storage.set_managed_connector_enabled(cloud_dir, "ihora", enabled=True)

    update_tool = {
        "name": "update_project_member",
        "action": "update_project_member",
        "description": "Mettre a jour un membre",
        "effect": "write",
        "visibility": "guided",
        "input_schema": {
            "type": "object",
            "properties": {
                "projectId": {"type": ["string", "number"]},
                "userId": {"type": ["string", "number"]},
                "email": {"type": "string"},
                "role": {"type": "string"},
            },
            "required": ["projectId"],
            "additionalProperties": False,
        },
    }
    cloud_storage.save_known_managed_connectors(
        cloud_dir,
        [{"id": "ihora", "name": "Ihora", "tools": [update_tool]}],
    )

    client = CloudControlPlaneClient(
        base_url="https://cloud.test",
        plugin_data_dir=cloud_dir,
    )
    client.save_tokens({"access_token": "tok", "org_id": "org-a", "device_id": "dev-1"})

    async def fake_allowed(self: CloudControlPlaneClient) -> set[str]:
        return {"ihora"}

    gate_called = {"value": False}

    class CaptureGate(ConfirmationGate):
        async def request_effect(self, **kwargs):  # type: ignore[no-untyped-def]
            gate_called["value"] = True
            return "approved"

    monkeypatch.setattr(CloudControlPlaneClient, "fetch_allowed_connector_ids", fake_allowed)

    async def fake_invoke_remote(self, connector_id, payload, identity):  # type: ignore[no-untyped-def]
        if payload.get("action") == "list_users":
            return {"ok": True, "result": {"users": [], "action": "list_users"}}
        return {"ok": True, "result": {"action": "update_project_member"}}

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
    ctx = RunContext(
        deps=deps,
        model=TestModel(),
        usage=None,
        prompt=None,
        tool_call_id="tc-resolution-fail",
    )

    with pytest.raises(ModelRetry, match="list_users"):
        await invoke_managed_connector_impl(
            ctx,
            connector_id="ihora",
            payload={
                "action": "update_project_member",
                "projectId": 42,
                "email": "unknown.user@improba.ch",
                "role": "manager",
            },
            gate_tool_name="managed__ihora__update_project_member",
        )

    assert gate_called["value"] is False


@pytest.mark.asyncio
async def test_invoke_opens_separate_gateways_for_preresolve_and_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    plugins_root = cloud_dir.parent
    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.test"})
    cloud_storage.set_managed_connector_enabled(cloud_dir, "ihora", enabled=True)

    update_tool = {
        "name": "update_project_member",
        "action": "update_project_member",
        "description": "Mettre a jour un membre",
        "effect": "write",
        "visibility": "guided",
        "input_schema": {
            "type": "object",
            "properties": {
                "projectId": {"type": ["string", "number"]},
                "userId": {"type": ["string", "number"]},
                "email": {"type": "string"},
                "role": {"type": "string"},
            },
            "required": ["projectId"],
            "additionalProperties": False,
        },
    }
    cloud_storage.save_known_managed_connectors(
        cloud_dir,
        [{"id": "ihora", "name": "Ihora", "tools": [update_tool]}],
    )

    client = CloudControlPlaneClient(
        base_url="https://cloud.test",
        plugin_data_dir=cloud_dir,
    )
    client.save_tokens({"access_token": "tok", "org_id": "org-a", "device_id": "dev-1"})

    async def fake_allowed(self: CloudControlPlaneClient) -> set[str]:
        return {"ihora"}

    class CaptureGate(ConfirmationGate):
        async def request_effect(self, **kwargs):  # type: ignore[no-untyped-def]
            return "approved"

    monkeypatch.setattr(CloudControlPlaneClient, "fetch_allowed_connector_ids", fake_allowed)

    gateway_calls: list[dict[str, object]] = []

    async def fake_invoke_remote(self, connector_id, payload, identity):  # type: ignore[no-untyped-def]
        if payload.get("action") == "list_users":
            return {
                "ok": True,
                "result": {
                    "users": [
                        {
                            "userId": 7,
                            "email": "sylvain.meylan@improba.ch",
                            "firstname": "Sylvain",
                            "lastname": "Meylan",
                        }
                    ],
                    "action": "list_users",
                },
            }
        return {"ok": True, "result": {"action": "update_project_member"}}

    def fake_open_gateway(**kwargs):  # type: ignore[no-untyped-def]
        gateway_calls.append(kwargs)
        return type("GW", (), {"invoke_remote": fake_invoke_remote})()

    monkeypatch.setattr(
        "app.plugins.workproba_cloud.plugin.open_remote_capability_gateway",
        fake_open_gateway,
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
    ctx = RunContext(
        deps=deps,
        model=TestModel(),
        usage=None,
        prompt=None,
        tool_call_id="tc-gateway-split",
    )

    await invoke_managed_connector_impl(
        ctx,
        connector_id="ihora",
        payload={
            "action": "update_project_member",
            "projectId": 42,
            "email": "sylvain.meylan@improba.ch",
            "role": "manager",
        },
        gate_tool_name="managed__ihora__update_project_member",
    )

    assert len(gateway_calls) == 2
    assert gateway_calls[0]["timeout_seconds"] == LIST_USERS_PRERESOLVE_TIMEOUT_SECONDS
    write_timeout = gateway_calls[1].get(
        "timeout_seconds", DEFAULT_REMOTE_TIMEOUT_SECONDS
    )
    assert write_timeout == DEFAULT_REMOTE_TIMEOUT_SECONDS
    assert write_timeout != LIST_USERS_PRERESOLVE_TIMEOUT_SECONDS


@pytest.mark.asyncio
async def test_preresolve_update_project_member_enriches_gate_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.plugins.workproba_cloud import storage as cloud_storage

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    plugins_root = cloud_dir.parent
    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.test"})
    cloud_storage.set_managed_connector_enabled(cloud_dir, "ihora", enabled=True)

    update_tool = {
        "name": "update_project_member",
        "action": "update_project_member",
        "description": "Mettre a jour un membre",
        "effect": "write",
        "visibility": "guided",
        "input_schema": {
            "type": "object",
            "properties": {
                "projectId": {"type": ["string", "number"]},
                "userId": {"type": ["string", "number"]},
                "email": {"type": "string"},
                "role": {"type": "string"},
            },
            "required": ["projectId"],
            "additionalProperties": False,
        },
    }
    cloud_storage.save_known_managed_connectors(
        cloud_dir,
        [{"id": "ihora", "name": "Ihora", "tools": [update_tool]}],
    )

    client = CloudControlPlaneClient(
        base_url="https://cloud.test",
        plugin_data_dir=cloud_dir,
    )
    client.save_tokens({"access_token": "tok", "org_id": "org-a", "device_id": "dev-1"})

    async def fake_allowed(self: CloudControlPlaneClient) -> set[str]:
        return {"ihora"}

    captured: dict[str, object] = {}

    class CaptureGate(ConfirmationGate):
        async def request_effect(self, **kwargs):  # type: ignore[no-untyped-def]
            captured["proposal"] = kwargs["proposal"]
            return "approved"

    monkeypatch.setattr(CloudControlPlaneClient, "fetch_allowed_connector_ids", fake_allowed)

    async def fake_invoke_remote(self, connector_id, payload, identity):  # type: ignore[no-untyped-def]
        if payload.get("action") == "list_users":
            return {
                "ok": True,
                "result": {
                    "users": [
                        {
                            "userId": 7,
                            "email": "sylvain.meylan@improba.ch",
                            "firstname": "Sylvain",
                            "lastname": "Meylan",
                        }
                    ],
                    "action": "list_users",
                },
            }
        captured["write_payload"] = payload
        return {"ok": True, "result": {"action": "update_project_member"}}

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
    ctx = RunContext(
        deps=deps,
        model=TestModel(),
        usage=None,
        prompt=None,
        tool_call_id="tc-preresolve",
    )

    payload = {
        "action": "update_project_member",
        "projectId": 42,
        "email": "sylvain.meylan@improba.ch",
        "role": "manager",
    }
    await invoke_managed_connector_impl(
        ctx,
        connector_id="ihora",
        payload=payload,
        gate_tool_name="managed__ihora__update_project_member",
    )

    proposal = captured.get("proposal")
    assert proposal is not None
    assert "Sylvain Meylan" in proposal.human_summary
    assert "sylvain.meylan@improba.ch" in proposal.human_summary
    assert "userId 7" in proposal.human_summary
    write_payload = captured.get("write_payload")
    assert isinstance(write_payload, dict)
    assert write_payload.get("userId") == 7
