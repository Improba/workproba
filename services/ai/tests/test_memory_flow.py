"""Tests de flux logiques bout-en-bout (promotion → injection, oubli, dédup)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.models.test import TestModel

import app.auth as authmod
import app.main as mainmod
from app.agent.tools import ToolContext, ToolDeps, build_agent
from app.memory_stores import open_memory_store_for_scope
from app.sandbox.runner import SandboxRunner
from conftest import FakeProjectClient

HEADERS = {"X-Internal-Secret": "desktop-dev-secret"}


@pytest.fixture(autouse=True)
def _patch_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)


@pytest.fixture
def workspace_data_dir(tmp_path: Path) -> Path:
    ws = tmp_path / "space-data"
    conv = ws / "conversations"
    conv.mkdir(parents=True)
    (conv / "other.json").write_text(
        json.dumps(
            {
                "id": "other",
                "title": "Budget RH",
                "summary": "Le budget annuel RH est de 120k€",
                "updatedAt": "2026-07-10T12:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    return ws


async def _fake_extract_budget(summary, **kwargs):  # noqa: ANN001, ANN003
    return ["Le budget RH annuel est fixé à 120k€"]


def _memory_prompt_fn(agent):
    for runner in agent._system_prompt_functions:
        if runner.function.__name__ == "memory_prompt":
            return runner.function
    raise AssertionError("memory_prompt not registered")


def _relevant_sessions_prompt_fn(agent):
    for runner in agent._system_prompt_functions:
        if runner.function.__name__ == "relevant_sessions_prompt":
            return runner.function
    raise AssertionError("relevant_sessions_prompt not registered")


class _FakeRunContext:
    def __init__(self, deps: ToolDeps) -> None:
        self.deps = deps


def test_flow_manual_add_dedup_via_http(workspace_data_dir: Path) -> None:
    """POST /memory/add deux fois un fait quasi identique → un seul souvenir."""
    with TestClient(mainmod.app) as client:
        for content in (
            "Le client préfère les exports Excel",
            "Le client préfère les exports Excel.",
        ):
            response = client.post(
                "/memory/add",
                headers=HEADERS,
                json={
                    "workspace_data_dir": str(workspace_data_dir),
                    "memory_scope": "project",
                    "content": content,
                },
            )
            assert response.status_code == 200

        listed = client.get(
            "/memory/items",
            params={"workspace_data_dir": str(workspace_data_dir)},
            headers=HEADERS,
        )
        assert listed.status_code == 200
        memories = listed.json()["memories"]
        assert len(memories) == 1


def test_flow_promote_then_memory_prompt_includes_fact(
    workspace_data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Promotion HTTP → le fait promu est injecté via memory_prompt."""
    monkeypatch.setattr(
        "app.agent.memory_consolidation.extract_facts_from_summary",
        _fake_extract_budget,
    )

    with TestClient(mainmod.app) as client:
        response = client.post(
            "/memory/promote-session",
            headers=HEADERS,
            json={
                "workspace_data_dir": str(workspace_data_dir),
                "session_id": "sess-promo",
                "summary": "Discussion budget RH annuel.",
                "locale": "fr",
            },
        )
        assert response.status_code == 200

    agent = build_agent(TestModel(), locale="fr")
    prompt_fn = _memory_prompt_fn(agent)
    ctx = _FakeRunContext(
        ToolDeps(
            context=ToolContext(
                tenant_id="t",
                project_id="p",
                session_id="current",
                documents=[],
                workspace_data_dir=workspace_data_dir,
                locale="fr",
                last_user_query="budget RH annuel",
            ),
            project_client=FakeProjectClient(),
            sandbox_runner=SandboxRunner(timeout_seconds=10),
        )
    )
    text = prompt_fn(ctx)
    assert "120k" in text


def test_flow_promote_then_skips_session_bridge(
    workspace_data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Après promotion, relevant_sessions_prompt n'injecte plus le résumé bridgé."""
    monkeypatch.setattr(
        "app.agent.memory_consolidation.extract_facts_from_summary",
        _fake_extract_budget,
    )

    with TestClient(mainmod.app) as client:
        response = client.post(
            "/memory/promote-session",
            headers=HEADERS,
            json={
                "workspace_data_dir": str(workspace_data_dir),
                "session_id": "other",
                "summary": "Le budget annuel RH est de 120k€",
                "locale": "fr",
            },
        )
        assert response.status_code == 200

    store = open_memory_store_for_scope("project", workspace_data_dir)
    try:
        assert any(
            "session:other" in (memory.get("tags") or [])
            for memory in store.list_memories()
        )
    finally:
        store.close()

    agent = build_agent(TestModel(), locale="fr")
    prompt_fn = _relevant_sessions_prompt_fn(agent)
    ctx = _FakeRunContext(
        ToolDeps(
            context=ToolContext(
                tenant_id="t",
                project_id="p",
                session_id="current",
                documents=[],
                workspace_data_dir=workspace_data_dir,
                locale="fr",
                last_user_query="budget RH annuel",
            ),
            project_client=FakeProjectClient(),
            sandbox_runner=SandboxRunner(timeout_seconds=10),
        )
    )
    assert prompt_fn(ctx) == ""


def test_flow_clear_user_scope_preserves_project_memories(tmp_path: Path) -> None:
    """Effacer la mémoire user ne touche pas aux souvenirs project."""
    app_data = tmp_path / "workproba-appdata"
    ws = app_data / "workspaces" / "ws1"
    ws.mkdir(parents=True)

    with TestClient(mainmod.app) as client:
        project_resp = client.post(
            "/memory/add",
            headers=HEADERS,
            json={
                "workspace_data_dir": str(ws),
                "memory_scope": "project",
                "content": "Spécifique à l'espace",
            },
        )
        assert project_resp.status_code == 200
        project_id = project_resp.json()["memory"]["id"]

        user_resp = client.post(
            "/memory/add",
            headers=HEADERS,
            json={
                "workspace_data_dir": str(ws),
                "memory_scope": "user",
                "content": "Préférence globale",
            },
        )
        assert user_resp.status_code == 200

        clear_resp = client.request(
            "DELETE",
            "/memory",
            headers=HEADERS,
            json={
                "workspace_data_dir": str(ws),
                "memory_scope": "user",
                "scope": "memories",
                "confirmed": True,
            },
        )
        assert clear_resp.status_code == 200

        user_items = client.get(
            "/memory/items",
            params={"workspace_data_dir": str(ws), "memory_scope": "user"},
            headers=HEADERS,
        ).json()["memories"]
        project_items = client.get(
            "/memory/items",
            params={"workspace_data_dir": str(ws), "memory_scope": "project"},
            headers=HEADERS,
        ).json()["memories"]

    assert user_items == []
    assert len(project_items) == 1
    assert project_items[0]["id"] == project_id


def test_flow_promote_twice_no_duplicate_facts(
    workspace_data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deux promotions identiques sur la même session → pas de doublon."""
    monkeypatch.setattr(
        "app.agent.memory_consolidation.extract_facts_from_summary",
        _fake_extract_budget,
    )

    payload = {
        "workspace_data_dir": str(workspace_data_dir),
        "session_id": "sess-dup",
        "summary": "Budget RH annuel discuté.",
        "locale": "fr",
    }
    with TestClient(mainmod.app) as client:
        for _ in range(2):
            response = client.post(
                "/memory/promote-session",
                headers=HEADERS,
                json=payload,
            )
            assert response.status_code == 200

        listed = client.get(
            "/memory/items",
            params={"workspace_data_dir": str(workspace_data_dir)},
            headers=HEADERS,
        )
        assert listed.status_code == 200
        memories = listed.json()["memories"]

    assert len(memories) == 1
    assert memories[0]["source"] == "session_promotion"


def test_flow_clear_project_scope_preserves_user_memories(tmp_path: Path) -> None:
    """Effacer la mémoire project ne touche pas aux souvenirs user."""
    app_data = tmp_path / "workproba-appdata"
    ws = app_data / "workspaces" / "ws1"
    ws.mkdir(parents=True)

    with TestClient(mainmod.app) as client:
        user_resp = client.post(
            "/memory/add",
            headers=HEADERS,
            json={
                "workspace_data_dir": str(ws),
                "memory_scope": "user",
                "content": "Préférence globale",
            },
        )
        assert user_resp.status_code == 200
        user_id = user_resp.json()["memory"]["id"]

        client.post(
            "/memory/add",
            headers=HEADERS,
            json={
                "workspace_data_dir": str(ws),
                "memory_scope": "project",
                "content": "Spécifique à l'espace",
            },
        )

        clear_resp = client.request(
            "DELETE",
            "/memory",
            headers=HEADERS,
            json={
                "workspace_data_dir": str(ws),
                "memory_scope": "project",
                "scope": "memories",
                "confirmed": True,
            },
        )
        assert clear_resp.status_code == 200

        user_items = client.get(
            "/memory/items",
            params={"workspace_data_dir": str(ws), "memory_scope": "user"},
            headers=HEADERS,
        ).json()["memories"]
        project_items = client.get(
            "/memory/items",
            params={"workspace_data_dir": str(ws), "memory_scope": "project"},
            headers=HEADERS,
        ).json()["memories"]

    assert len(user_items) == 1
    assert user_items[0]["id"] == user_id
    assert project_items == []
