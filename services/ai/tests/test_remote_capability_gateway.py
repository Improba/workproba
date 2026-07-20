"""Tests RemoteCapabilityGateway scaffold (T-V3-CP-3)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from app.plugins.ports.remote_capability_gateway import (
    REMOTE_CAPABILITY_PERMISSION,
    HttpRemoteCapabilityGateway,
    IdentityDelegation,
    LocalRemoteCapabilityGateway,
    RemoteCapabilityRejected,
    clear_remote_capability_audit_log,
    minimize_remote_payload,
    open_remote_capability_gateway,
    remote_capability_audit_log,
)
from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD


def _plugins_root(tmp_path: Path) -> Path:
    root = tmp_path / "app_data" / "plugins"
    root.mkdir(parents=True)
    return root


def test_minimize_remote_payload_strips_local_data() -> None:
    payload = {
        "action": "sync",
        "workspace_data_dir": "/secret/ws",
        "project_path": "/secret/project",
        "conversations": [{"role": "user", "content": "hi"}],
        "nested": {"local_files": ["a.txt"], "keep": True},
        "items": [{"conversation": "leak", "ok": 1}, {"keep": 2}],
    }
    minimized = minimize_remote_payload(payload)
    assert "workspace_data_dir" not in minimized
    assert "project_path" not in minimized
    assert "conversations" not in minimized
    assert minimized["action"] == "sync"
    assert minimized["nested"] == {"keep": True}
    assert minimized["items"] == [{"ok": 1}, {"keep": 2}]


def test_open_remote_capability_gateway_requires_permission(tmp_path: Path) -> None:
    plugins_root = _plugins_root(tmp_path)
    with pytest.raises(PermissionError, match=REMOTE_CAPABILITY_PERMISSION):
        open_remote_capability_gateway(
            caller_plugin_id=PLUGIN_WORKPROBA_CLOUD,
            caller_permissions=frozenset({"storage:namespace"}),
            plugins_root=plugins_root,
        )


@pytest.mark.asyncio
async def test_local_stub_rejects_by_default(tmp_path: Path) -> None:
    clear_remote_capability_audit_log()
    plugins_root = _plugins_root(tmp_path)
    gateway = open_remote_capability_gateway(
        caller_plugin_id=PLUGIN_WORKPROBA_CLOUD,
        caller_permissions=frozenset({REMOTE_CAPABILITY_PERMISSION}),
        plugins_root=plugins_root,
    )
    identity = IdentityDelegation(subject_id="user-1", org_id="org-1")

    with pytest.raises(RemoteCapabilityRejected, match="not allowed"):
        await gateway.invoke_remote("workproba.personas", {"action": "ping"}, identity)

    audit = remote_capability_audit_log()
    assert any(entry["op"] == "invoke_rejected" for entry in audit)


@pytest.mark.asyncio
async def test_local_stub_allows_configured_capability(tmp_path: Path) -> None:
    plugins_root = _plugins_root(tmp_path)
    gateway = LocalRemoteCapabilityGateway(
        caller_plugin_id=PLUGIN_WORKPROBA_CLOUD,
        app_data_dir=tmp_path / "app_data",
        allowed_capability_ids=frozenset({"demo.cap"}),
    )
    result = await gateway.invoke_remote(
        "demo.cap",
        {"action": "ping", "conversations": []},
        IdentityDelegation(subject_id="user-1"),
    )
    assert result["ok"] is True
    assert result["capability_id"] == "demo.cap"
    assert "conversations" not in result.get("payload_keys", [])


@pytest.mark.asyncio
async def test_local_stub_timeout(tmp_path: Path) -> None:
    class SlowGateway(LocalRemoteCapabilityGateway):
        async def _invoke_allowed(self, capability_id, payload, identity_delegation):
            await asyncio.sleep(0.05)
            return {"ok": True}

    gateway = SlowGateway(
        caller_plugin_id=PLUGIN_WORKPROBA_CLOUD,
        app_data_dir=tmp_path / "app_data",
        allowed_capability_ids=frozenset({"slow.cap"}),
        timeout_seconds=0.01,
    )
    with pytest.raises(RemoteCapabilityRejected, match="timed out"):
        await gateway.invoke_remote(
            "slow.cap",
            {"action": "wait"},
            IdentityDelegation(subject_id="user-1"),
        )


@pytest.mark.asyncio
async def test_http_gateway_surfaces_server_error_body(tmp_path: Path) -> None:
    clear_remote_capability_audit_log()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"statusCode": 403, "message": "connector_not_allowed:echo"},
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
    with pytest.raises(RemoteCapabilityRejected, match="connector_not_allowed:echo"):
        await gateway.invoke_remote(
            "echo",
            {"ping": True},
            IdentityDelegation(subject_id="dev-1", access_token="tok"),
        )


@pytest.mark.asyncio
async def test_http_gateway_mock_transport(tmp_path: Path) -> None:
    clear_remote_capability_audit_log()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/connectors/demo.cap/invoke"
        body = __import__("json").loads(request.content.decode("utf-8"))
        assert "conversations" not in body["payload"]
        assert "identity" not in body
        return httpx.Response(200, json={"ok": True, "remote": True})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="https://remote.test")
    gateway = HttpRemoteCapabilityGateway(
        base_url="https://remote.test",
        caller_plugin_id=PLUGIN_WORKPROBA_CLOUD,
        app_data_dir=tmp_path / "app_data",
        allowed_capability_ids=frozenset({"demo.cap"}),
        http_client=client,
    )
    result = await gateway.invoke_remote(
        "demo.cap",
        {"action": "sync", "conversations": [{"x": 1}]},
        IdentityDelegation(subject_id="user-42", access_token="tok"),
    )
    assert result["remote"] is True
    assert any(entry["op"] == "invoke_remote" for entry in remote_capability_audit_log())
