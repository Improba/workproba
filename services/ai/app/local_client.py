import asyncio
import base64
import logging
import mimetypes
from pathlib import Path
from typing import Any

from app.documents.extractor import LocalExtractor, is_binary_document
from app.limits import DEFAULT_LIMITS, Limits
from app.project_client import ProjectClient
from app.rag.store import RagStore
from app.schemas import (
    DocumentContent,
    FileEntry,
    FileListResponse,
    KnowledgeSearchResponse,
    KnowledgeSearchResult,
)
from app.versions import snapshot_before_overwrite

logger = logging.getLogger(__name__)


# Dossiers ignorés lors du scan de recherche (substring fallback).
IGNORED_DIRS = {".git", ".workproba", ".venv", "__pycache__", "node_modules"}


class LocalProjectClient(ProjectClient):
    """Project client backed by local files for the desktop sidecar.

    Toutes les lectures/écritures appliquent les plafonds définis dans `Limits`
    (défense en profondeur) : la taille renvoyée au LLM est bornée quel que soit le
    volume réel sur disque.
    """

    def __init__(
        self,
        *,
        project_root: Path | str,
        workspace_data_dir: Path | str | None = None,
        extractor: LocalExtractor | None = None,
        rag_store: RagStore | None = None,
        limits: Limits = DEFAULT_LIMITS,
    ) -> None:
        self._project_root = Path(project_root).expanduser().resolve()
        _ = workspace_data_dir
        self._limits = limits
        self._extractor = extractor or LocalExtractor(limits=limits)
        self._rag_store = rag_store

    async def close(self) -> None:
        if self._rag_store is not None:
            self._rag_store.close()

    async def search_kb(
        self,
        *,
        tenant_id: str,
        project_id: str,
        query: str,
        limit: int = 8,
        filters: dict[str, Any] | None = None,
    ) -> KnowledgeSearchResponse:
        _ = (tenant_id, project_id, filters)

        clamped_limit = self._clamp_search_limit(limit)

        if self._rag_store is not None and query.strip():
            try:
                vector_results = await self._rag_store.search(
                    query=query, limit=clamped_limit
                )
            except Exception as exc:
                logger.warning("RAG vector search failed, fallback to substring: %s", exc)
                vector_results = []
            if vector_results:
                return KnowledgeSearchResponse(
                    results=[
                        KnowledgeSearchResult(
                            document_id=item["document_id"],
                            title=item.get("title") or item["document_id"],
                            content=item["content"],
                            score=item.get("score"),
                            metadata={
                                **(item.get("metadata") or {}),
                                "path": item["document_id"],
                                "source": "rag",
                                "mime_type": item.get("mime_type"),
                            },
                        )
                        for item in vector_results
                    ]
                )

        return await asyncio.to_thread(
            self._substring_search, query=query, limit=clamped_limit
        )

    async def list_files(
        self,
        *,
        subdir: str = "",
        max_entries: int = 0,
    ) -> FileListResponse:
        """Liste bornée de l'arborescence projet (fichiers + dossiers).

        `subdir` est un chemin relatif optionnel sous la racine projet ; il est
        validé pour ne pas s'échapper de la racine. Le parcours ignore les
        dossiers sensibles (`.git`, `.workproba`, `node_modules`, ...) et plafonne
        le nombre d'entrées et la profondeur pour éviter l'explosion.
        """
        return await asyncio.to_thread(
            self._list_files_sync, subdir=subdir, max_entries=max_entries
        )

    def _list_files_sync(self, *, subdir: str, max_entries: int) -> FileListResponse:
        if subdir.strip():
            base = self._resolve_relative_path(subdir)
        else:
            base = self._project_root
        if not base.exists() or not base.is_dir():
            raise FileNotFoundError(f"Directory not found: {subdir or '.'}")

        cap = max_entries if max_entries and max_entries > 0 else self._limits.list_max_entries
        cap = min(cap, self._limits.list_max_entries)
        max_depth = self._limits.list_max_depth

        entries: list[FileEntry] = []
        scanned = 0
        truncated = False
        reason: str | None = None

        def walk(dir_path: Path, depth: int) -> None:
            nonlocal scanned, truncated, reason
            if truncated or depth > max_depth:
                return
            try:
                children = sorted(
                    dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
                )
            except OSError:
                return
            for child in children:
                if scanned >= cap:
                    truncated = True
                    reason = "max_entries"
                    return
                if self._is_ignored(child):
                    continue
                try:
                    rel = child.relative_to(self._project_root).as_posix()
                except ValueError:
                    continue
                is_dir = child.is_dir()
                size = 0
                if not is_dir:
                    try:
                        size = child.stat().st_size
                    except OSError:
                        size = 0
                scanned += 1
                entries.append(
                    FileEntry(
                        path=rel,
                        name=child.name,
                        is_dir=is_dir,
                        size_bytes=size,
                        kind="folder" if is_dir else self._classify_kind(child),
                    )
                )
                if is_dir:
                    walk(child, depth + 1)
                    if truncated:
                        return

        walk(base, 0)
        return FileListResponse(
            root=self._project_root.as_posix(),
            entries=entries,
            truncated=truncated,
            truncation_reason=reason,
            metadata={
                "subdir": subdir or ".",
                "scanned": scanned,
                "max_entries": cap,
                "max_depth": max_depth,
            },
        )

    async def read_document(
        self,
        *,
        tenant_id: str,
        project_id: str,
        document_id: str,
        offset_lines: int = 0,
        max_lines: int = 0,
    ) -> DocumentContent:
        _ = (tenant_id, project_id)
        if offset_lines < 0:
            raise ValueError("offset_lines must be >= 0")
        path = self._resolve_relative_path(document_id)
        if not path.is_file():
            raise FileNotFoundError(f"Document not found: {document_id}")

        relative_path = path.relative_to(self._project_root).as_posix()
        mime_type, _encoding = mimetypes.guess_type(path.name)
        size_bytes = path.stat().st_size

        if is_binary_document(path.name, mime_type):
            if size_bytes > self._limits.extract_max_input_bytes:
                raise ValueError(
                    f"Document binaire trop volumineux pour extraction : "
                    f"{size_bytes} octets > {self._limits.extract_max_input_bytes}. "
                    f"Utilise search_kb ou découpe le fichier."
                )
            extracted = await self._extractor.extract(
                content=path.read_bytes(),
                filename=path.name,
                mime_type=mime_type,
            )
            metadata = {
                **extracted.metadata,
                "path": relative_path,
                "size_bytes": size_bytes,
                "source": "local",
                "extracted": True,
            }
            text = extracted.text
            await self._index_if_enabled(
                document_id=relative_path,
                title=path.name,
                mime_type=mime_type,
                text=text,
            )
            return DocumentContent(
                document_id=relative_path,
                name=path.name,
                mime_type=mime_type,
                text=text,
                metadata=metadata,
            )

        # Lecture texte en flux : on ne charge jamais le fichier entier en mémoire.
        effective_max_lines = max_lines if max_lines and max_lines > 0 else self._limits.read_max_lines
        effective_max_lines = min(effective_max_lines, self._limits.read_max_lines)
        text, lines_returned, bytes_returned, truncated, reason = self._read_text_window(
            path,
            offset_lines=offset_lines,
            max_lines=effective_max_lines,
            max_bytes=self._limits.read_max_bytes,
        )
        await self._index_if_enabled(
            document_id=relative_path,
            title=path.name,
            mime_type=mime_type,
            text=text,
        )
        return DocumentContent(
            document_id=relative_path,
            name=path.name,
            mime_type=mime_type,
            text=text,
            metadata={
                "path": relative_path,
                "size_bytes": size_bytes,
                "source": "local",
                "offset_lines": offset_lines,
                "lines_returned": lines_returned,
                "bytes_returned": bytes_returned,
                "truncated": truncated,
                "truncation_reason": reason,
            },
        )

    async def _index_if_enabled(
        self,
        *,
        document_id: str,
        title: str,
        mime_type: str | None,
        text: str,
    ) -> None:
        if self._rag_store is None or not text.strip():
            return
        try:
            await self._rag_store.index_document(
                document_id=document_id,
                title=title,
                mime_type=mime_type,
                text=text,
            )
        except Exception as exc:
            logger.warning("RAG indexing failed for %s: %s", document_id, exc)

    # --- recherche substring (en thread, budget borné) ---------------------

    def _clamp_search_limit(self, limit: int) -> int:
        try:
            value = int(limit)
        except (TypeError, ValueError):
            return self._limits.search_max_limit
        return max(1, min(value, self._limits.search_max_limit))

    def _substring_search(self, *, query: str, limit: int) -> KnowledgeSearchResponse:
        query_normalized = query.casefold()
        results: list[KnowledgeSearchResult] = []

        if not self._project_root.exists():
            return KnowledgeSearchResponse(results=results)

        scanned = 0
        max_files = self._limits.search_max_files
        for path in self._project_root.rglob("*"):
            if scanned >= max_files:
                logger.info(
                    "Substring search stopped at %d scanned files (budget reached).",
                    max_files,
                )
                break
            if len(results) >= limit:
                break
            if not path.is_file() or self._is_ignored(path):
                continue
            scanned += 1

            relative_path = path.relative_to(self._project_root).as_posix()
            filename_matches = (
                not query_normalized or query_normalized in relative_path.casefold()
            )
            content = self._read_search_text(path)
            content_index = (
                content.casefold().find(query_normalized) if query_normalized else -1
            )

            if not filename_matches and content_index < 0:
                continue

            snippet = self._build_snippet(content, content_index)
            results.append(
                KnowledgeSearchResult(
                    document_id=relative_path,
                    title=path.name,
                    content=snippet or relative_path,
                    score=1.0 if content_index >= 0 else 0.5,
                    metadata={
                        "path": relative_path,
                        "source": "local",
                        "scanned_files": scanned,
                    },
                )
            )

        return KnowledgeSearchResponse(results=results)

    # --- génération de documents -------------------------------------------

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
        _ = (tenant_id, project_id)
        content = base64.b64decode(content_base64, validate=True)
        if len(content) > self._limits.generate_max_bytes:
            raise ValueError(
                f"Generated document too large: {len(content)} bytes > "
                f"{self._limits.generate_max_bytes} bytes."
            )

        target_path = self._resolve_relative_path(name)
        relative_path = target_path.relative_to(self._project_root).as_posix()
        if self._is_denied_path(relative_path):
            raise ValueError(
                f"Writing to this path is not allowed: {relative_path}"
            )

        target_path.parent.mkdir(parents=True, exist_ok=True)

        version_entry = snapshot_before_overwrite(
            project_root=self._project_root,
            session_id=session_id,
            relative_path=relative_path,
        )
        version_relative_path = (
            str(version_entry["snapshot_path"]) if version_entry else None
        )

        target_path.write_bytes(content)

        # On ne renvoie pas le contenu intégral au LLM : un accusé de création
        # (chemin + taille) suffit et évite l'écho du document dans le contexte.
        return DocumentContent(
            document_id=relative_path,
            name=target_path.name,
            mime_type=mime_type,
            text=None,
            metadata={
                **(metadata or {}),
                "path": relative_path,
                "version_path": version_relative_path,
                "size_bytes": len(content),
                "source": "local",
                "saved": True,
            },
        )

    # --- helpers -----------------------------------------------------------

    def _resolve_relative_path(self, relative_path: str) -> Path:
        if not relative_path.strip():
            raise ValueError("Path must not be empty.")

        path = (self._project_root / relative_path).expanduser().resolve()
        if not path.is_relative_to(self._project_root):
            raise ValueError(f"Path escapes project root: {relative_path}")
        return path

    def _is_ignored(self, path: Path) -> bool:
        relative_parts = path.relative_to(self._project_root).parts
        return any(part in IGNORED_DIRS for part in relative_parts)

    def _classify_kind(self, path: Path) -> str:
        ext = path.suffix.lower().lstrip(".")
        if ext in {"xls", "xlsx", "csv"}:
            return "table"
        if ext in {"doc", "docx", "ppt", "pptx"}:
            return "report"
        if ext == "pdf":
            return "source"
        if ext in {"html", "htm"}:
            return "html"
        if ext in {"md", "txt"}:
            return "text"
        return "file"

    def _is_denied_path(self, relative_path: str) -> bool:
        parts = Path(relative_path).parts
        for part in parts:
            if part in self._limits.generate_deny_names:
                return True
            for prefix in self._limits.generate_deny_prefixes:
                if part.startswith(prefix):
                    return True
        return False

    def _read_search_text(self, path: Path) -> str:
        try:
            if path.stat().st_size > self._limits.search_file_max_bytes:
                return ""
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def _build_snippet(self, content: str, content_index: int) -> str:
        if not content:
            return ""
        if content_index < 0:
            return content[:240]

        start = max(0, content_index - 120)
        end = min(len(content), content_index + 240)
        return content[start:end].strip()

    def _read_text_window(
        self,
        path: Path,
        *,
        offset_lines: int,
        max_lines: int,
        max_bytes: int,
    ) -> tuple[str, int, int, bool, str | None]:
        """Lit un fichier texte par fenêtre (offset + limite lignes + budget octets).

        Ne charge jamais le fichier entier en mémoire : on lit ligne par ligne et
        on stoppe dès qu'un plafond est atteint. Retourne
        (text, lines_returned, bytes_returned, truncated, reason).
        """
        returned: list[str] = []
        bytes_acc = 0
        lines_acc = 0
        truncated = False
        reason: str | None = None

        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for _ in range(offset_lines):
                if not handle.readline():
                    break
            while True:
                if lines_acc >= max_lines:
                    truncated = True
                    reason = "max_lines"
                    break
                line = handle.readline()
                if line == "":
                    break
                line_bytes = len(line.encode("utf-8", errors="replace"))
                if bytes_acc + line_bytes > max_bytes:
                    truncated = True
                    reason = "max_bytes"
                    break
                returned.append(line)
                bytes_acc += line_bytes
                lines_acc += 1

        return "".join(returned), lines_acc, bytes_acc, truncated, reason
