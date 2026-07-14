"""Tests du journal d'audit local JSONL."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import APITimeoutError
from pydantic_ai.models.test import TestModel

import app.auth as authmod
import app.main as mainmod
from app.agent.loop import AgentLoop
from app.audit import (
    audit_file_path,
    get_audit_config,
    log_event,
    read_audit,
    resolve_app_data_dir,
    rotate,
    save_audit_config,
)
from app.plugins.core import CoreAPI, clear_cross_audit_log, cross_audit_log
from app.plugins.hooks import PluginContext
from app.rag.store import open_memory_store
from app.versions import restore_version, snapshot_before_overwrite

INTERNAL_HEADERS = {"X-Internal-Secret": "desktop-dev-secret"}


@pytest.fixture(autouse=True)
def _patch_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)


def _app_data(tmp_path: Path) -> Path:
    app_data = tmp_path / "app_data"
    app_data.mkdir()
    (app_data / "spaces" / "space-1").mkdir(parents=True)
    return app_data


def test_log_event_and_read(tmp_path: Path) -> None:
    app_data = _app_data(tmp_path)
    log_event(app_data, "browser.navigate", "agent", {"url": "https://example.com"})
    entries, total = read_audit(app_data, event="browser.navigate")
    assert total == 1
    assert entries[0]["event"] == "browser.navigate"
    assert entries[0]["actor"] == "agent"
    assert entries[0]["details"]["url"] == "https://example.com"
    assert audit_file_path(app_data).is_file()


def test_rotate_removes_old_entries(tmp_path: Path) -> None:
    app_data = _app_data(tmp_path)
    audit_path = audit_file_path(app_data)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    old_ts = (datetime.now(UTC) - timedelta(days=120)).isoformat()
    recent_ts = datetime.now(UTC).isoformat()
    lines = [
        json.dumps({"timestamp": old_ts, "event": "old", "actor": "user", "details": {}}),
        json.dumps({"timestamp": recent_ts, "event": "recent", "actor": "user", "details": {}}),
    ]
    audit_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    removed = rotate(app_data, retention_days=90)
    assert removed == 1
    entries, total = read_audit(app_data)
    assert total == 1
    assert entries[0]["event"] == "recent"


def test_audit_config_defaults_and_update(tmp_path: Path) -> None:
    app_data = _app_data(tmp_path)
    config = get_audit_config(app_data)
    assert config["retention_days"] == 90
    assert config["enabled"] is True
    updated = save_audit_config(app_data, retention_days=30, enabled=False)
    assert updated == {"retention_days": 30, "enabled": False}


def test_resolve_app_data_from_workspace(tmp_path: Path) -> None:
    app_data = _app_data(tmp_path)
    workspace = app_data / "spaces" / "space-1"
    assert resolve_app_data_dir(workspace) == app_data


def test_version_restore_is_audited(tmp_path: Path) -> None:
    app_data = _app_data(tmp_path)
    workspace = app_data / "spaces" / "space-1"
    project = tmp_path / "project"
    project.mkdir()
    target = project / "doc.txt"
    target.write_text("v1", encoding="utf-8")
    first = snapshot_before_overwrite(
        workspace_data_dir=workspace,
        project_root=project,
        relative_path="doc.txt",
    )
    assert first is not None
    target.write_text("v2", encoding="utf-8")
    restore_version(
        workspace_data_dir=workspace,
        project_root=project,
        file_path="doc.txt",
        version_id=str(first["version_id"]),
    )
    entries, _ = read_audit(app_data, event="version.restore")
    assert len(entries) == 1
    assert entries[0]["details"]["file_path"] == "doc.txt"


def test_memory_forget_is_audited(tmp_path: Path) -> None:
    app_data = _app_data(tmp_path)
    workspace = app_data / "spaces" / "space-1"
    store = open_memory_store(workspace / "memory.db")
    try:
        created = store.add_memory(content="souvenir test", source="user")
        store.forget_memory(str(created["id"]))
        store.clear_all(scope="all")
    finally:
        store.close()
    entries, _ = read_audit(app_data)
    events = {entry["event"] for entry in entries}
    assert "memory.forget" in events
    assert "memory.forget_all" in events


def test_plugin_cross_is_audited(tmp_path: Path) -> None:
    clear_cross_audit_log()
    app_data = _app_data(tmp_path)
    plugins_root = app_data / "plugins"
    source_dir = plugins_root / "workproba.cloud"
    target_dir = plugins_root / "workproba.projet"
    source_dir.mkdir(parents=True)
    target_dir.mkdir(parents=True)
    ctx = PluginContext(
        plugin_id="workproba.cloud",
        plugin_data_dir=source_dir,
        locale="fr",
        provider_set=None,
        permissions=frozenset(["storage:cross:workproba.projet"]),
    )
    core = CoreAPI.for_plugin(ctx)
    core.storage.cross("workproba.projet", "set", "sync_marker", "ok")
    assert len(cross_audit_log()) == 1
    entries, _ = read_audit(app_data, event="plugin.cross")
    assert len(entries) == 1
    assert entries[0]["details"]["target"] == "workproba.projet"


def test_audit_http_endpoints(tmp_path: Path) -> None:
    app_data = _app_data(tmp_path)
    workspace = app_data / "spaces" / "space-1"
    log_event(app_data, "publish_artifact", "user", {"project_id": "p1", "name": "doc.pdf"})
    with TestClient(mainmod.app) as client:
        list_resp = client.get(
            "/audit",
            params={"workspace_data_dir": str(workspace), "event": "publish_artifact"},
            headers=INTERNAL_HEADERS,
        )
        assert list_resp.status_code == 200
        body = list_resp.json()
        assert body["total"] == 1
        assert body["entries"][0]["event"] == "publish_artifact"

        config_resp = client.get(
            "/audit/config",
            params={"workspace_data_dir": str(workspace)},
            headers=INTERNAL_HEADERS,
        )
        assert config_resp.status_code == 200
        assert config_resp.json()["retention_days"] == 90

        locked_resp = client.post(
            "/audit/config",
            json={
                "workspace_data_dir": str(workspace),
                "retention_days": 14,
                "settings_locked": True,
            },
            headers=INTERNAL_HEADERS,
        )
        assert locked_resp.status_code == 403

        update_resp = client.post(
            "/audit/config",
            json={
                "workspace_data_dir": str(workspace),
                "retention_days": 14,
            },
            headers=INTERNAL_HEADERS,
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["retention_days"] == 14


def test_audit_http_filters_from_to_aliases(tmp_path: Path) -> None:
    app_data = _app_data(tmp_path)
    workspace = app_data / "spaces" / "space-1"
    old_ts = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    recent_ts = datetime.now(UTC).isoformat()
    audit_path = audit_file_path(app_data)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({"timestamp": old_ts, "event": "old", "actor": "user", "details": {}}),
        json.dumps({"timestamp": recent_ts, "event": "recent", "actor": "user", "details": {}}),
    ]
    audit_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    cutoff = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    with TestClient(mainmod.app) as client:
        list_resp = client.get(
            "/audit",
            params={
                "workspace_data_dir": str(workspace),
                "from": cutoff,
            },
            headers=INTERNAL_HEADERS,
        )
        assert list_resp.status_code == 200
        body = list_resp.json()
        assert body["total"] == 1
        assert body["entries"][0]["event"] == "recent"


def test_turn_prompt_audited_when_enabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mainmod, "build_model", lambda config: TestModel(seed=0, call_tools=[]))
    app_data = _app_data(tmp_path)
    workspace = app_data / "spaces" / "space-1"
    project = tmp_path / "project"
    project.mkdir()

    payload = {
        "tenant_id": "t",
        "project_id": "p1",
        "project_path": str(project),
        "workspace_data_dir": str(workspace),
        "workspace_title": "Espace test",
        "session_id": "sess-audit-prompt",
        "message": "bonjour",
        "history": [],
        "documents": [],
        "audit_enabled": True,
        "llm_provider_config": {
            "provider": "ollama",
            "model": "llama3.2",
        },
    }

    with TestClient(mainmod.app) as client:
        with client.stream(
            "POST",
            "/agent/turn",
            json=payload,
            headers=INTERNAL_HEADERS,
        ) as resp:
            assert resp.status_code == 200
            for _line in resp.iter_lines():
                pass

    entries, total = read_audit(app_data, event="turn.prompt")
    assert total == 1
    details = entries[0]["details"]
    assert details["session_id"] == "sess-audit-prompt"
    assert details["provider"] == "ollama"
    assert details["model"] == "llama3.2"
    assert details["variables"]["workspace_title"] == "Espace test"
    assert details["combined_sha256"]
    assert any(ref["kind"] == "static" for ref in details["prompt_refs"])
    assert any(ref["kind"] == "dynamic" for ref in details["prompt_refs"])
    serialized = json.dumps(details)
    assert "bonjour" not in serialized


def test_turn_prompt_not_audited_when_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mainmod, "build_model", lambda config: TestModel(seed=0, call_tools=[]))
    app_data = _app_data(tmp_path)
    workspace = app_data / "spaces" / "space-1"
    project = tmp_path / "project"
    project.mkdir()

    payload = {
        "tenant_id": "t",
        "project_id": "p1",
        "project_path": str(project),
        "workspace_data_dir": str(workspace),
        "session_id": "sess-audit-off",
        "message": "hello",
        "history": [],
        "documents": [],
        "audit_enabled": False,
        "llm_provider_config": {
            "provider": "ollama",
            "model": "llama3.2",
        },
    }

    with TestClient(mainmod.app) as client:
        with client.stream(
            "POST",
            "/agent/turn",
            json=payload,
            headers=INTERNAL_HEADERS,
        ) as resp:
            assert resp.status_code == 200
            for _line in resp.iter_lines():
                pass

    entries, total = read_audit(app_data, event="turn.prompt")
    assert total == 0


def test_turn_prompt_not_duplicated_on_provider_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un repli provider ne doit pas émettre un second événement turn.prompt."""
    monkeypatch.setattr(mainmod, "build_model", lambda config: TestModel(seed=0, call_tools=[]))

    original = AgentLoop._iter_model_stream
    call_count = {"n": 0}

    async def fail_once_then_succeed(
        self: AgentLoop, node: Any, ctx: Any
    ) -> AsyncIterator[Any]:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise APITimeoutError(request=httpx.Request("POST", "http://example.test/v1/chat"))
        async for event in original(self, node, ctx):
            yield event

    monkeypatch.setattr(AgentLoop, "_iter_model_stream", fail_once_then_succeed)

    app_data = _app_data(tmp_path)
    workspace = app_data / "spaces" / "space-1"
    project = tmp_path / "project"
    project.mkdir()

    payload = {
        "tenant_id": "t",
        "project_id": "p1",
        "project_path": str(project),
        "workspace_data_dir": str(workspace),
        "session_id": "sess-fallback-audit",
        "message": "hello",
        "history": [],
        "documents": [],
        "audit_enabled": True,
        "provider_set": {
            "id": "test-fallback-audit",
            "chat": {
                "provider": "mistral",
                "model": "mistral-small-latest",
                "api_key": "primary-key",
            },
            "chat_fallback": {
                "provider": "ollama",
                "model": "llama3.2",
            },
        },
    }

    with TestClient(mainmod.app) as client:
        with client.stream(
            "POST",
            "/agent/turn",
            json=payload,
            headers=INTERNAL_HEADERS,
        ) as resp:
            assert resp.status_code == 200
            for _line in resp.iter_lines():
                pass

    assert call_count["n"] >= 2

    prompt_entries, prompt_total = read_audit(app_data, event="turn.prompt")
    assert prompt_total == 1
    assert prompt_entries[0]["details"]["session_id"] == "sess-fallback-audit"

    fallback_entries, fallback_total = read_audit(app_data, event="provider.fallback")
    assert fallback_total == 1
