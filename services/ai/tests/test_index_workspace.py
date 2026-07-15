"""Tests de l'indexation RAG bulk du workspace (`LocalProjectClient.index_workspace`
et endpoint `/agent/index-workspace`).

Pas de réseau : le `RagStore` réel est remplacé par un `FakeRagStore` qui
enregistre les appels `index_document` sans appeler d'embedding.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import app.auth as authmod
import app.main as mainmod
from app.limits import Limits
from app.local_client import LocalProjectClient


class FakeRagStore:
    """Store RAG en mémoire : enregistre les documents indexés (pas d'embedding)."""

    def __init__(self, db_path: Path | str = "<fake>") -> None:
        self.db_path = Path(db_path)
        self.indexed: list[dict[str, Any]] = []
        # Empreintes injectables pour simuler un document déjà indexé.
        self.fingerprints: dict[str, tuple[float, int]] = {}

    async def index_document(
        self,
        *,
        document_id: str,
        title: str,
        mime_type: str | None,
        text: str,
        source: str = "local",
        metadata: dict[str, Any] | None = None,
        mtime: float | None = None,
        size: int | None = None,
    ) -> int:
        if mtime is not None and size is not None:
            self.fingerprints[document_id] = (mtime, size)
        self.indexed.append(
            {
                "document_id": document_id,
                "title": title,
                "mime_type": mime_type,
                "text": text,
            }
        )
        return len(text)

    async def search(self, *, query: str, limit: int = 8) -> list[dict[str, Any]]:
        return []

    def document_fingerprint(self, document_id: str) -> tuple[float, int] | None:
        return self.fingerprints.get(document_id)

    def close(self) -> None:
        return None


def _client(tmp_path: Path, store: FakeRagStore | None, limits: Limits | None = None) -> LocalProjectClient:
    return LocalProjectClient(
        project_root=tmp_path,
        limits=limits or Limits(),
        rag_store=store,
    )


def _make_tree(root: Path) -> None:
    (root / "rapport.md").write_text("# Rapport Q2\n\nCA en hausse de 12%.", encoding="utf-8")
    (root / "notes.txt").write_text("Support client priorité Q3.", encoding="utf-8")
    (root / "data").mkdir()
    (root / "data" / "chiffres.csv").write_text("mois,ca\n07,12345\n", encoding="utf-8")
    (root / "data" / "config.json").write_text('{"k": 1}', encoding="utf-8")
    # Dossiers ignorés
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("git", encoding="utf-8")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "x.js").write_text("module.exports=1", encoding="utf-8")
    (root / "vendor").mkdir()
    (root / "vendor" / "lib.php").write_text("<?php", encoding="utf-8")
    # Secret
    (root / ".env").write_text("MISTRAL_API_KEY=secret", encoding="utf-8")
    # Binaire opaque non Office -> ignoré
    (root / "archive.zip").write_bytes(b"PK\x03\x04")


# --- index_workspace : cas unitaires ----------------------------------------


def test_index_workspace_disabled_when_no_store(tmp_path: Path) -> None:
    client = _client(tmp_path, store=None)
    report = asyncio.run(client.index_workspace())
    assert report.enabled is False
    assert report.indexed == 0
    assert report.metadata["reason"] == "rag_disabled"


def test_index_workspace_indexes_text_files(tmp_path: Path) -> None:
    _make_tree(tmp_path)
    store = FakeRagStore()
    client = _client(tmp_path, store)

    report = asyncio.run(client.index_workspace())

    assert report.enabled is True
    assert report.indexed == 4
    indexed_ids = {item["document_id"] for item in store.indexed}
    assert indexed_ids == {"rapport.md", "notes.txt", "data/chiffres.csv", "data/config.json"}
    # Le contenu texte est bien passé au store.
    rapport = next(item for item in store.indexed if item["document_id"] == "rapport.md")
    assert "hausse de 12%" in rapport["text"]


def test_index_workspace_skips_ignored_dirs_and_secrets(tmp_path: Path) -> None:
    _make_tree(tmp_path)
    store = FakeRagStore()
    client = _client(tmp_path, store)

    report = asyncio.run(client.index_workspace())

    indexed_ids = {item["document_id"] for item in store.indexed}
    assert not any(p.startswith(".git") for p in indexed_ids)
    assert not any(p.startswith("node_modules") for p in indexed_ids)
    assert not any(p.startswith("vendor") for p in indexed_ids)
    assert ".env" not in indexed_ids
    # Les chemins sensibles (`.env`) sont filtrés avant collecte : jamais scannés.
    assert ".env" not in report.skipped_paths


def test_index_workspace_skips_unsupported_binary(tmp_path: Path) -> None:
    _make_tree(tmp_path)
    store = FakeRagStore()
    client = _client(tmp_path, store)

    asyncio.run(client.index_workspace())

    indexed_ids = {item["document_id"] for item in store.indexed}
    assert "archive.zip" not in indexed_ids


def test_index_workspace_skips_large_text(tmp_path: Path) -> None:
    (tmp_path / "big.txt").write_text("x" * 2048, encoding="utf-8")
    (tmp_path / "ok.txt").write_text("ok", encoding="utf-8")
    store = FakeRagStore()
    client = _client(tmp_path, store, limits=Limits(index_max_file_bytes=512))

    report = asyncio.run(client.index_workspace())

    indexed_ids = {item["document_id"] for item in store.indexed}
    assert indexed_ids == {"ok.txt"}
    assert "big.txt" in report.skipped_paths


def test_index_workspace_total_chars_budget_truncates(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a" * 100, encoding="utf-8")
    (tmp_path / "b.txt").write_text("b" * 100, encoding="utf-8")
    (tmp_path / "c.txt").write_text("c" * 100, encoding="utf-8")
    store = FakeRagStore()
    client = _client(tmp_path, store, limits=Limits(index_max_total_chars=150))

    report = asyncio.run(client.index_workspace())

    assert report.truncated is True
    assert report.truncation_reason == "max_total_chars"
    # On indexe tant que le budget le permet, puis on stoppe.
    assert report.indexed >= 1
    assert report.total_chars <= 150


def test_index_workspace_respects_max_files(tmp_path: Path) -> None:
    for i in range(10):
        (tmp_path / f"f{i}.txt").write_text(f"f{i}", encoding="utf-8")
    store = FakeRagStore()
    client = _client(tmp_path, store)

    report = asyncio.run(client.index_workspace(max_files=3))

    assert report.indexed == 3
    assert report.scanned == 3  # le parcours s'arrête au cap
    assert report.truncated is True
    assert report.truncation_reason == "max_files"


def test_index_workspace_indexes_extensionless_text(tmp_path: Path) -> None:
    (tmp_path / "Makefile").write_text("all: build\nbuild:\n\techo ok", encoding="utf-8")
    (tmp_path / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    store = FakeRagStore()
    client = _client(tmp_path, store)

    asyncio.run(client.index_workspace())

    indexed_ids = {item["document_id"] for item in store.indexed}
    assert "Makefile" in indexed_ids
    assert "Dockerfile" in indexed_ids


def test_index_workspace_no_overflow_when_under_cap(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    store = FakeRagStore()
    client = _client(tmp_path, store)

    report = asyncio.run(client.index_workspace(max_files=100))

    assert report.truncated is False
    assert report.truncation_reason is None


def test_index_workspace_skips_unchanged_files(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    store = FakeRagStore()
    client = _client(tmp_path, store)

    first = asyncio.run(client.index_workspace())
    assert first.indexed == 2
    assert first.unchanged == 0

    # Second passage sans modification : tout est « unchanged », rien ré-indexé.
    second = asyncio.run(client.index_workspace())
    assert second.indexed == 0
    assert second.unchanged == 2


def test_index_workspace_reindexes_modified_file(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    store = FakeRagStore()
    client = _client(tmp_path, store)

    asyncio.run(client.index_workspace())
    # On modifie le fichier (mtime + contenu changent).
    (tmp_path / "a.txt").write_text("aa", encoding="utf-8")

    report = asyncio.run(client.index_workspace())
    assert report.indexed == 1
    assert report.unchanged == 0


def test_index_workspace_paths_restricts_scope(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    (tmp_path / "c.txt").write_text("c", encoding="utf-8")
    store = FakeRagStore()
    client = _client(tmp_path, store)

    report = asyncio.run(client.index_workspace(paths=["b.txt", "c.txt"]))

    assert report.metadata["incremental"] is True
    assert {item["document_id"] for item in store.indexed} == {"b.txt", "c.txt"}
    assert report.scanned == 2


def test_index_workspace_paths_ignores_out_of_root(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    store = FakeRagStore()
    client = _client(tmp_path, store)

    report = asyncio.run(client.index_workspace(paths=["../escape.txt", "a.txt"]))

    assert {item["document_id"] for item in store.indexed} == {"a.txt"}


def test_index_workspace_indexes_docx(tmp_path: Path) -> None:
    from docx import Document
    from io import BytesIO

    doc = Document()
    doc.add_paragraph("Contenu Word pour le RAG bulk.")
    buf = BytesIO()
    doc.save(buf)
    (tmp_path / "note.docx").write_bytes(buf.getvalue())

    store = FakeRagStore()
    client = _client(tmp_path, store)

    report = asyncio.run(client.index_workspace())

    assert "note.docx" in {item["document_id"] for item in store.indexed}
    note = next(item for item in store.indexed if item["document_id"] == "note.docx")
    assert "RAG bulk" in note["text"]


# --- endpoint HTTP ----------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)


def test_index_workspace_endpoint_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Simule un sidecar sans modèle d'embedding configuré.
    monkeypatch.setattr(mainmod, "build_rag_store", lambda *a, **k: None)
    with TestClient(mainmod.app) as client:
        resp = client.post(
            "/agent/index-workspace",
            json={"project_path": str(tmp_path), "project_id": str(tmp_path)},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False
    assert body["indexed"] == 0
    assert body["metadata"]["reason"] == "rag_disabled"


def test_index_workspace_endpoint_indexes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_tree(tmp_path)
    fake_store = FakeRagStore(db_path=tmp_path / "memory.db")
    monkeypatch.setattr(mainmod, "build_rag_store", lambda *a, **k: fake_store)

    with TestClient(mainmod.app) as client:
        resp = client.post(
            "/agent/index-workspace",
            json={"project_path": str(tmp_path), "project_id": str(tmp_path)},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is True
    assert body["indexed"] == 4
    assert set(body["indexed_paths"]) == {
        "rapport.md", "notes.txt", "data/chiffres.csv", "data/config.json"
    }
