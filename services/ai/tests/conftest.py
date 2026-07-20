"""Pytest shared fixtures for the Workproba AI sidecar tests."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import SecretStr

from app.project_client import ProjectClient
from app.schemas import (
    DocumentContent,
    FileEntry,
    FileListResponse,
    KnowledgeSearchResponse,
    KnowledgeSearchResult,
    LLMProviderConfig,
)


class FakeProjectClient(ProjectClient):
    """In-memory project client for deterministic agent/HTTP tests (no FS, no LLM)."""

    def __init__(
        self,
        *,
        documents: dict[str, str] | None = None,
        file_entries: list[tuple[str, bool, int]] | None = None,
    ) -> None:
        self._documents = documents or {}
        # (relative_path, is_dir, size_bytes) — optionnel, sinon dérivé des documents.
        self._file_entries = file_entries
        self.saved: list[dict[str, Any]] = []

    async def close(self) -> None:
        return None

    async def list_files(
        self,
        *,
        subdir: str = "",
        max_entries: int = 0,
    ) -> FileListResponse:
        cap = max_entries if max_entries and max_entries > 0 else 500
        prefix = f"{subdir.strip().strip('/')}/" if subdir.strip() else ""

        if self._file_entries is not None:
            raw = self._file_entries
        else:
            raw = [(path, False, len(content)) for path, content in self._documents.items()]

        entries: list[FileEntry] = []
        truncated = False
        for path, is_dir, size in sorted(raw, key=lambda item: item[0]):
            if prefix and not path.startswith(prefix):
                continue
            if len(entries) >= cap:
                truncated = True
                break
            entries.append(
                FileEntry(
                    path=path,
                    name=path.rsplit("/", 1)[-1],
                    is_dir=is_dir,
                    size_bytes=size,
                    kind="folder" if is_dir else "file",
                )
            )
        return FileListResponse(
            root="<fake>",
            entries=entries,
            truncated=truncated,
            truncation_reason="max_entries" if truncated else None,
            metadata={"subdir": subdir or "."},
        )

    async def search_kb(
        self,
        *,
        tenant_id: str,
        project_id: str,
        query: str,
        limit: int = 8,
        filters: dict[str, Any] | None = None,
    ) -> KnowledgeSearchResponse:
        _ = (tenant_id, project_id, filters, limit)
        results = [
            KnowledgeSearchResult(
                document_id=doc_id,
                title=doc_id,
                content=content,
                score=1.0,
                metadata={"source": "fake"},
            )
            for doc_id, content in self._documents.items()
            if query.lower() in content.lower() or query.lower() in doc_id.lower()
        ]
        return KnowledgeSearchResponse(results=results)

    async def read_document(
        self,
        *,
        tenant_id: str,
        project_id: str,
        document_id: str,
        offset_lines: int = 0,
        max_lines: int = 0,
    ) -> DocumentContent:
        _ = (tenant_id, project_id, offset_lines, max_lines)
        if document_id not in self._documents:
            raise FileNotFoundError(f"Document not found: {document_id}")
        return DocumentContent(
            document_id=document_id,
            name=document_id,
            mime_type="text/plain",
            text=self._documents[document_id],
            metadata={"source": "fake"},
        )

    async def save_generated_document(
        self,
        *,
        tenant_id: str,
        project_id: str,
        session_id: str,
        name: str,
        mime_type: str,
        content_base64: str,
        metadata: dict[str, Any] | None = None,
    ) -> DocumentContent:
        _ = (tenant_id, project_id, session_id)
        self.saved.append(
            {
                "name": name,
                "mime_type": mime_type,
                "metadata": metadata,
                "content_base64": content_base64,
            }
        )
        return DocumentContent(
            document_id=name,
            name=name,
            mime_type=mime_type,
            text="(saved)",
            metadata=metadata or {},
        )


@pytest.fixture
def fake_project_client() -> FakeProjectClient:
    return FakeProjectClient(
        documents={
            "rapport.md": "Le CA Q2 atteint 12345 EUR, hausse de 12%.",
            "notes.md": "Le support client est la priorite Q3.",
        }
    )


@pytest.fixture
def mistral_config() -> LLMProviderConfig:
    return LLMProviderConfig(
        provider="mistral",
        model="mistral-small-latest",
        base_url="https://api.mistral.ai/v1",
        api_key=SecretStr("test-key"),
        temperature=0.3,
        max_tokens=512,
        extra_headers={"X-Test": "yes"},
    )
