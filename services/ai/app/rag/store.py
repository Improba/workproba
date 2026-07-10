"""RAG vector store local (SQLite + sqlite-vec) pour Workproba.

La base vit par workspace : `{workspace_data_dir}/memory.db` (ou `.workproba/memory.db`).
Embeddings via LiteLLM (Ollama, Mistral, OpenAI…). Si aucun modèle d'embedding
n'est configuré, le store reste désactivé et la recherche retombe sur lesubstring (côté client).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import litellm
import sqlite_vec

_EMBEDDING_DIM_UNKNOWN = -1


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
                indexed_at TEXT
            )
            """
        )
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
        conn.commit()
        self._conn = conn
        return conn

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
            "INSERT OR REPLACE INTO documents(document_id, title, mime_type, source, indexed_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            (document_id, title, mime_type, source),
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

    async def search(
        self,
        *,
        query: str,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        if self._dim == _EMBEDDING_DIM_UNKNOWN:
            # Pas encore indexé -> rien à chercher.
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

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
