"""Tests mémoire étendue (souvenirs explicites, oubli, tout oublier)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.auth as authmod
import app.main as mainmod
from app.rag.store import RagStore, clear_conversations, open_memory_store
from app.versions import snapshot_before_overwrite, versions_dir_for_file


@pytest.fixture(autouse=True)
def _patch_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)


@pytest.fixture
def workspace_data_dir(tmp_path: Path) -> Path:
    ws = tmp_path / "space-data"
    ws.mkdir()
    conv = ws / "conversations"
    conv.mkdir()
    (conv / "sess-1.json").write_text(
        json.dumps({"id": "sess-1", "title": "Test"}),
        encoding="utf-8",
    )
    return ws


@pytest.fixture
def memory_store(workspace_data_dir: Path) -> RagStore:
    store = open_memory_store(workspace_data_dir / "memory.db")
    yield store
    store.close()


def test_list_and_add_memories(memory_store: RagStore) -> None:
    assert memory_store.list_memories() == []
    entry = memory_store.add_memory(
        content="Le user préfère les exports Excel.",
        source="manual",
        tags=["preference"],
    )
    memories = memory_store.list_memories()
    assert len(memories) == 1
    assert memories[0]["id"] == entry["id"]
    assert memories[0]["tags"] == ["preference"]


def test_forget_memory(memory_store: RagStore) -> None:
    entry = memory_store.add_memory(content="Fait temporaire", source="manual")
    assert memory_store.forget_memory(entry["id"]) is True
    assert memory_store.list_memories() == []
    assert memory_store.forget_memory(entry["id"]) is False


def test_search_combined_includes_explicit_memory(memory_store: RagStore) -> None:
    memory_store.add_memory(content="Le budget RH est de 120k€", source="manual")
    results = asyncio.run(memory_store.search_combined(query="budget", limit=5))
    assert any(item.get("kind") == "memory" for item in results)


def test_clear_all_keeps_versions(workspace_data_dir: Path, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    target = project / "note.txt"
    target.write_text("v1", encoding="utf-8")
    snapshot_before_overwrite(
        workspace_data_dir=workspace_data_dir,
        project_root=project,
        relative_path="note.txt",
    )

    store = open_memory_store(workspace_data_dir / "memory.db")
    store.add_memory(content="Souvenir", source="manual")
    store.clear_all()
    assert store.list_memories() == []
    store.close()

    version_dir = versions_dir_for_file(workspace_data_dir, "note.txt")
    assert (version_dir / "manifest.json").is_file()


def test_memory_items_http(workspace_data_dir: Path) -> None:
    store = open_memory_store(workspace_data_dir / "memory.db")
    entry = store.add_memory(content="Préférence PDF", source="manual")
    store.close()

    headers = {"X-Internal-Secret": "desktop-dev-secret"}
    with TestClient(mainmod.app) as client:
        resp = client.get(
            "/memory/items",
            params={"workspace_data_dir": str(workspace_data_dir)},
            headers=headers,
        )
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["memories"]]
        assert entry["id"] in ids


def test_memory_forget_http(workspace_data_dir: Path) -> None:
    store = open_memory_store(workspace_data_dir / "memory.db")
    entry = store.add_memory(content="À oublier", source="manual")
    store.close()

    headers = {"X-Internal-Secret": "desktop-dev-secret"}
    with TestClient(mainmod.app) as client:
        resp = client.post(
            "/memory/forget",
            json={
                "workspace_data_dir": str(workspace_data_dir),
                "memory_id": entry["id"],
            },
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


def test_memory_clear_requires_confirmation(workspace_data_dir: Path) -> None:
    headers = {"X-Internal-Secret": "desktop-dev-secret"}
    with TestClient(mainmod.app) as client:
        resp = client.request(
            "DELETE",
            "/memory",
            json={
                "workspace_data_dir": str(workspace_data_dir),
                "scope": "all",
                "confirmed": False,
            },
            headers=headers,
        )
        assert resp.status_code == 400


def test_memory_clear_all_scope(workspace_data_dir: Path) -> None:
    store = open_memory_store(workspace_data_dir / "memory.db")
    store.add_memory(content="Souvenir", source="manual")
    store.close()
    assert (workspace_data_dir / "conversations" / "sess-1.json").is_file()

    headers = {"X-Internal-Secret": "desktop-dev-secret"}
    with TestClient(mainmod.app) as client:
        resp = client.request(
            "DELETE",
            "/memory",
            json={
                "workspace_data_dir": str(workspace_data_dir),
                "scope": "all",
                "confirmed": True,
            },
            headers=headers,
        )
        assert resp.status_code == 200

    store = open_memory_store(workspace_data_dir / "memory.db")
    assert store.list_memories() == []
    store.close()
    assert not (workspace_data_dir / "conversations" / "sess-1.json").is_file()


def test_memory_clear_memories_scope_keeps_conversations(
    workspace_data_dir: Path,
) -> None:
    """Scope memories : efface les souvenirs projet sans toucher aux conversations."""
    store = open_memory_store(workspace_data_dir / "memory.db")
    store.add_memory(content="Souvenir", source="manual")
    store.close()
    assert (workspace_data_dir / "conversations" / "sess-1.json").is_file()

    headers = {"X-Internal-Secret": "desktop-dev-secret"}
    with TestClient(mainmod.app) as client:
        resp = client.request(
            "DELETE",
            "/memory",
            json={
                "workspace_data_dir": str(workspace_data_dir),
                "scope": "memories",
                "confirmed": True,
            },
            headers=headers,
        )
        assert resp.status_code == 200

    store = open_memory_store(workspace_data_dir / "memory.db")
    assert store.list_memories() == []
    store.close()
    assert (workspace_data_dir / "conversations" / "sess-1.json").is_file()


def test_memory_clear_conversations_scope(workspace_data_dir: Path) -> None:
    store = open_memory_store(workspace_data_dir / "memory.db")
    store.add_memory(content="Souvenir", source="manual")
    store.close()

    removed = clear_conversations(workspace_data_dir)
    assert removed == 1
    assert not (workspace_data_dir / "conversations" / "sess-1.json").is_file()

    store = open_memory_store(workspace_data_dir / "memory.db")
    assert len(store.list_memories()) == 1
    store.close()


def test_versions_rotation_fifo(workspace_data_dir: Path, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    target = project / "doc.txt"
    target.write_text("base", encoding="utf-8")

    for index in range(55):
        target.write_text(f"v{index}", encoding="utf-8")
        snapshot_before_overwrite(
            workspace_data_dir=workspace_data_dir,
            project_root=project,
            relative_path="doc.txt",
            max_versions=50,
        )

    version_dir = versions_dir_for_file(workspace_data_dir, "doc.txt")
    manifest = json.loads((version_dir / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 50
