"""RAG vector store local (SQLite + sqlite-vec) pour Workproba.

La base vit par workspace : `{workspace_data_dir}/memory.db` (ou `.workproba/memory.db`).
Embeddings via LiteLLM (Ollama, Mistral, OpenAI…). Si aucun modèle d'embedding
n'est configuré, le store reste désactivé et la recherche retombe sur lesubstring (côté client).
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import litellm
import sqlite_vec

from app.audit import log_event, resolve_app_data_dir

_EMBEDDING_DIM_UNKNOWN = -1


class RagStoreProtocol(Protocol):
    """Contrat structural attendu par `LocalProjectClient` pour le RAG.

    Permet d'injecter un faux store dans les tests sans dépendre de la classe
    concrète `RagStore` (pas d'appel réseau / embedding).
    """

    @property
    def db_path(self) -> Path: ...

    async def index_document(
        self,
        *,
        document_id: str,
        title: str,
        mime_type: str | None,
        text: str,
        source: str = ...,
        metadata: dict[str, Any] | None = ...,
        mtime: float | None = ...,
        size: int | None = ...,
    ) -> int: ...

    async def search(
        self,
        *,
        query: str,
        limit: int = ...,
    ) -> list[dict[str, Any]]: ...

    def document_fingerprint(self, document_id: str) -> tuple[float, int] | None: ...

    def close(self) -> None: ...


def chunk_text(text: str, *, chunk_size: int = 1_200, overlap: int = 120) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be lower than chunk_size")

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


class RagStore:
    """Vector store SQLite + sqlite-vec, embeddings via LiteLLM."""

    def __init__(
        self,
        *,
        db_path: Path,
        embedding_model: str,
        embedding_base_url: str | None = None,
        embedding_api_key: str | None = None,
    ) -> None:
        self._db_path = db_path
        self._embedding_model = embedding_model
        self._embedding_base_url = embedding_base_url
        self._embedding_api_key = embedding_api_key
        self._conn: sqlite3.Connection | None = None
        self._dim: int = _EMBEDDING_DIM_UNKNOWN

    @property
    def db_path(self) -> Path:
        return self._db_path

    def _connect(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                document_id TEXT PRIMARY KEY,
                title TEXT,
                mime_type TEXT,
                source TEXT,
                indexed_at TEXT,
                mtime REAL,
                size INTEGER
            )
            """
        )
        self._migrate_documents_columns(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT,
                chunk_index INTEGER,
                content TEXT,
                metadata TEXT
            )
            """
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                source TEXT,
                created_at TEXT NOT NULL,
                tags TEXT
            )
            """
        )
        conn.commit()
        self._conn = conn
        return conn

    @staticmethod
    def _migrate_documents_columns(conn: sqlite3.Connection) -> None:
        """Ajoute `mtime`/`size` aux bases existantes (idempotent)."""
        cols = {row[1] for row in conn.execute("PRAGMA table_info(documents)")}
        if "mtime" not in cols:
            conn.execute("ALTER TABLE documents ADD COLUMN mtime REAL")
        if "size" not in cols:
            conn.execute("ALTER TABLE documents ADD COLUMN size INTEGER")

    def _ensure_vec_table(self, dim: int) -> None:
        conn = self._connect()
        stored = conn.execute(
            "SELECT value FROM meta WHERE key = 'embedding_dim'"
        ).fetchone()
        if stored is None:
            conn.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0("
                f"id INTEGER PRIMARY KEY, embedding float[{dim}])"
            )
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES ('embedding_dim', ?)",
                (str(dim),),
            )
            conn.commit()
            self._dim = dim
        else:
            self._dim = int(stored[0])
            if self._dim != dim:
                raise ValueError(
                    f"Embedding dimension mismatch: store expects {self._dim}, "
                    f"model returned {dim}. Reindex required."
                )

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        kwargs: dict[str, Any] = {
            "model": self._embedding_model,
            "input": texts,
        }
        if self._embedding_base_url:
            kwargs["api_base"] = self._embedding_base_url
        if self._embedding_api_key:
            kwargs["api_key"] = self._embedding_api_key
        response = await litellm.aembedding(**kwargs)
        return [item["embedding"] for item in response.data]

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
        if not text.strip():
            return 0
        chunks = chunk_text(text)
        vectors = await self._embed(chunks)
        if not vectors:
            return 0
        dim = len(vectors[0])
        self._ensure_vec_table(dim)
        conn = self._connect()

        conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
        conn.execute(
            "INSERT OR REPLACE INTO documents(document_id, title, mime_type, source, indexed_at, mtime, size) "
            "VALUES (?, ?, ?, ?, datetime('now'), ?, ?)",
            (document_id, title, mime_type, source, mtime, size),
        )
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        for chunk_index, (content, vector) in enumerate(zip(chunks, vectors, strict=True)):
            cur = conn.execute(
                "INSERT INTO chunks(document_id, chunk_index, content, metadata) VALUES (?, ?, ?, ?)",
                (document_id, chunk_index, content, meta_json),
            )
            conn.execute(
                "INSERT INTO vec_chunks(id, embedding) VALUES (?, ?)",
                (cur.lastrowid, json.dumps(vector)),
            )
        conn.commit()
        return len(chunks)

    def document_fingerprint(self, document_id: str) -> tuple[float, int] | None:
        """Retourne (mtime, size) du document indexé, ou None s'il n'existe pas.

        Utilisé pour l'indexation incrémentale : si un fichier a la même
        empreinte que la version indexée, on évite de le ré-extraire et
        ré-embarquer.
        """
        conn = self._connect()
        row = conn.execute(
            "SELECT mtime, size FROM documents WHERE document_id = ?",
            (document_id,),
        ).fetchone()
        if row is None:
            return None
        mtime, size = row
        if mtime is None or size is None:
            return None
        return float(mtime), int(size)

    async def search(
        self,
        *,
        query: str,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        if self._dim == _EMBEDDING_DIM_UNKNOWN:
            return []
        vectors = await self._embed([query])
        if not vectors:
            return []
        query_vector = json.dumps(vectors[0])
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT c.document_id, c.content, c.metadata, v.distance, d.title, d.mime_type
            FROM (
                SELECT id, distance
                FROM vec_chunks
                WHERE embedding MATCH ? AND k = ?
                ORDER BY distance
            ) v
            JOIN chunks c ON c.id = v.id
            JOIN documents d ON d.document_id = c.document_id
            """,
            (query_vector, limit),
        ).fetchall()
        results: list[dict[str, Any]] = []
        for document_id, content, metadata_json, distance, title, mime_type in rows:
            try:
                meta = json.loads(metadata_json) if metadata_json else {}
            except json.JSONDecodeError:
                meta = {}
            results.append(
                {
                    "document_id": document_id,
                    "title": title,
                    "mime_type": mime_type,
                    "content": content,
                    "score": max(0.0, 1.0 - float(distance)),
                    "metadata": meta,
                }
            )
        return results

    def list_memories(self) -> list[dict[str, Any]]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT id, content, source, created_at, tags FROM memories ORDER BY created_at DESC"
        ).fetchall()
        results: list[dict[str, Any]] = []
        for memory_id, content, source, created_at, tags_json in rows:
            tags: list[str] = []
            if tags_json:
                try:
                    parsed = json.loads(tags_json)
                    if isinstance(parsed, list):
                        tags = [str(tag) for tag in parsed]
                except json.JSONDecodeError:
                    tags = []
            results.append(
                {
                    "id": memory_id,
                    "content": content,
                    "source": source or "manual",
                    "created_at": created_at,
                    "tags": tags,
                }
            )
        return results

    def add_memory(
        self,
        *,
        content: str,
        source: str = "manual",
        tags: list[str] | None = None,
        memory_id: str | None = None,
    ) -> dict[str, Any]:
        cleaned = content.strip()
        if not cleaned:
            raise ValueError("empty_memory_content")
        conn = self._connect()
        entry_id = memory_id or f"mem_{uuid.uuid4().hex[:12]}"
        created_at = datetime.now(UTC).isoformat()
        tags_json = json.dumps(tags or [], ensure_ascii=False)
        conn.execute(
            "INSERT OR REPLACE INTO memories(id, content, source, created_at, tags) "
            "VALUES (?, ?, ?, ?, ?)",
            (entry_id, cleaned, source, created_at, tags_json),
        )
        conn.commit()
        return {
            "id": entry_id,
            "content": cleaned,
            "source": source,
            "created_at": created_at,
            "tags": tags or [],
        }

    def forget_memory(self, memory_id: str, *, actor: str = "user", scope: str = "memory") -> bool:
        conn = self._connect()
        cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        conn.commit()
        removed = cursor.rowcount > 0
        if removed:
            log_event(
                resolve_app_data_dir(self._db_path.parent),
                "memory.forget",
                actor,
                {"memory_id": memory_id, "scope": scope},
            )
        return removed

    def clear_memories(self) -> int:
        conn = self._connect()
        cursor = conn.execute("DELETE FROM memories")
        conn.commit()
        return int(cursor.rowcount)

    def clear_rag_index(self) -> None:
        conn = self._connect()
        conn.execute("DELETE FROM chunks")
        conn.execute("DELETE FROM documents")
        if self._dim != _EMBEDDING_DIM_UNKNOWN:
            conn.execute("DELETE FROM vec_chunks")
        conn.commit()

    def clear_all(self, *, actor: str = "user", scope: str = "all") -> dict[str, int]:
        memories_removed = self.clear_memories()
        self.clear_rag_index()
        log_event(
            resolve_app_data_dir(self._db_path.parent),
            "memory.forget_all",
            actor,
            {"scope": scope},
        )
        return {"memories_removed": memories_removed}

    async def search_combined(
        self,
        *,
        query: str,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        """Recherche RAG + correspondance textuelle sur les souvenirs explicites."""
        results: list[dict[str, Any]] = []
        rag_hits = await self.search(query=query, limit=limit)
        for hit in rag_hits:
            results.append({**hit, "kind": "rag"})
        needle = query.strip().lower()
        if needle:
            for memory in self.list_memories():
                content = str(memory.get("content") or "")
                if needle in content.lower():
                    results.append(
                        {
                            "kind": "memory",
                            "memory_id": memory.get("id"),
                            "content": content,
                            "source": memory.get("source"),
                            "score": 1.0,
                            "metadata": {"tags": memory.get("tags") or []},
                        }
                    )
        return results[:limit]

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


def clear_conversations(workspace_data_dir: Path) -> int:
    """Efface l'historique des conversations d'un espace (fichiers JSON)."""
    conv_dir = workspace_data_dir / "conversations"
    if not conv_dir.is_dir():
        return 0
    removed = 0
    for path in conv_dir.glob("*.json"):
        try:
            path.unlink()
            removed += 1
        except OSError:
            continue
    return removed


def open_memory_store(db_path: Path) -> RagStore:
    """Ouvre le store mémoire sans modèle d'embedding (souvenirs explicites seuls)."""
    return RagStore(
        db_path=db_path,
        embedding_model="disabled/local",
        embedding_base_url=None,
        embedding_api_key=None,
    )
