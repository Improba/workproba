from typing import Any, Protocol

from app.schemas import DocumentContent, FileListResponse, KnowledgeSearchResponse


class ProjectClient(Protocol):
    """Project I/O interface for the desktop sidecar."""

    async def close(self) -> None:
        ...

    async def list_files(
        self,
        *,
        subdir: str = "",
        max_entries: int = 0,
    ) -> FileListResponse:
        ...

    async def search_kb(
        self,
        *,
        tenant_id: str,
        project_id: str,
        query: str,
        limit: int = 8,
        filters: dict[str, Any] | None = None,
    ) -> KnowledgeSearchResponse:
        ...

    async def read_document(
        self,
        *,
        tenant_id: str,
        project_id: str,
        document_id: str,
        offset_lines: int = 0,
        max_lines: int = 0,
    ) -> DocumentContent:
        ...

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
        ...
