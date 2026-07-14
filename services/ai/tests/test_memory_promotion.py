"""Tests API promotion mémoire inter-session."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.auth as authmod
import app.main as mainmod
from app.rag.store import open_memory_store

HEADERS = {"X-Internal-Secret": "desktop-dev-secret"}


@pytest.fixture(autouse=True)
def _patch_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)


@pytest.fixture
def workspace_data_dir(tmp_path: Path) -> Path:
    ws = tmp_path / "space-data"
    ws.mkdir()
    return ws


async def _fake_extract(summary, **kwargs):  # noqa: ANN001, ANN003
    return ["Le client préfère les exports Excel."]


def test_memory_promote_session_endpoint(
    workspace_data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_promote(store, **kwargs):  # noqa: ANN001, ANN003
        return {
            "session_id": kwargs["session_id"],
            "facts": ["Le client préfère les exports Excel."],
            "results": [{"operation": "ADD"}],
            "counts": {"ADD": 1, "UPDATE": 0, "NOOP": 0, "DELETE": 0},
            "pruned": 0,
        }

    monkeypatch.setattr("app.main.promote_session_summary", _fake_promote)

    with TestClient(mainmod.app) as client:
        response = client.post(
            "/memory/promote-session",
            headers=HEADERS,
            json={
                "workspace_data_dir": str(workspace_data_dir),
                "session_id": "sess-1",
                "summary": "Le client a demandé des exports Excel.",
                "locale": "fr",
            },
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "sess-1"
    assert payload["facts"] == ["Le client préfère les exports Excel."]
    assert payload["counts"]["ADD"] == 1


def test_memory_promote_session_rejects_empty_summary(
    workspace_data_dir: Path,
) -> None:
    with TestClient(mainmod.app) as client:
        response = client.post(
            "/memory/promote-session",
            headers=HEADERS,
            json={
                "workspace_data_dir": str(workspace_data_dir),
                "session_id": "sess-1",
                "summary": "   ",
            },
        )
    assert response.status_code == 400


def test_memory_promote_session_integration(
    workspace_data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.agent.memory_consolidation.extract_facts_from_summary",
        _fake_extract,
    )

    with TestClient(mainmod.app) as client:
        response = client.post(
            "/memory/promote-session",
            headers=HEADERS,
            json={
                "workspace_data_dir": str(workspace_data_dir),
                "session_id": "sess-42",
                "summary": "Le client préfère les exports Excel pour le suivi.",
                "locale": "fr",
            },
        )
    assert response.status_code == 200

    store = open_memory_store(workspace_data_dir / "memory.db")
    try:
        memories = store.list_memories()
    finally:
        store.close()
    assert len(memories) == 1
    assert memories[0]["source"] == "session_promotion"
    assert "session:sess-42" in memories[0]["tags"]
