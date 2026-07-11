"""Outils Workproba exposés à l'agent Pydantic AI.

Chaque outil est une fonction typée async enregistrée via `@agent.tool` ;
Pydantic AI déduit le schéma JSON depuis la signature + docstring. Les deps
(`ToolDeps`) portent le contexte de tour et les clients projet/sandbox.

Toute exception levée par un outil est convertie en `ModelRetry` : l'échec
remonte côté UI via un `ToolCallResultEvent(is_error=True)` (RetryPromptPart)
et le modèle est informé pour s'adapter, comme le faisait l'ancien
`ToolRegistry.dispatch` (qui enveloppait les erreurs dans un ToolResult is_error).
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ModelRetry

from app.agent.confirmation import ConfirmationGate
from app.agent.human import build_human_summary
from app.agent.plan import PlanGate
from app.documents.writer import build_docx_bytes, build_pdf_bytes, build_xlsx_bytes
from app.i18n import DEFAULT_LOCALE, t
from app.limits import DEFAULT_LIMITS, Limits
from app.project_client import ProjectClient
from app.sandbox.runner import SandboxRunner
from app.schemas import DocumentReference, ProviderSet, UiMode

WORKPROBA_SYSTEM_PROMPT = t(DEFAULT_LOCALE, "tools.system_prompt")


def system_prompt_for_locale(locale: str = DEFAULT_LOCALE) -> str:
    return t(locale, "tools.system_prompt")


@dataclass(frozen=True)
class ToolContext:
    # Réservé multi-tenant futur ; ignoré par local_client.
    tenant_id: str
    project_id: str
    session_id: str
    documents: list[DocumentReference]
    project_root: Path | None = None
    workspace_data_dir: Path | None = None
    locale: str = DEFAULT_LOCALE
    active_plugins: list[str] | None = None
    plugin_data_dir: Path | None = None
    provider_set: ProviderSet | None = None
    settings_locked: bool = False
    permissions_network: bool = True
    code_execute: bool = True
    audit_retention_days: int | None = None
    audit_enabled: bool | None = None


@dataclass
class ToolDeps:
    context: ToolContext
    project_client: ProjectClient
    sandbox_runner: SandboxRunner
    limits: Limits = field(default_factory=lambda: DEFAULT_LIMITS)
    confirmation_gate: ConfirmationGate | None = None
    plan_gate: PlanGate | None = None


def _retry(exc: Exception) -> ModelRetry:
    return ModelRetry(f"{type(exc).__name__}: {exc}")


def _normalize_relative_path(file_path: str) -> str:
    normalized = file_path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _write_action(
    project_root: Path | None,
    name: str,
) -> tuple[str, Literal["create", "modify"]]:
    proposed_path = _normalize_relative_path(name)
    if project_root is None:
        return proposed_path, "create"
    target = (project_root / proposed_path).resolve()
    if target.is_file():
        return proposed_path, "modify"
    return proposed_path, "create"


def build_inventory_prompt(
    documents: list[DocumentReference],
    cap: int,
    locale: str = DEFAULT_LOCALE,
) -> str:
    """Construit le prompt système listant les fichiers projet transmis.

    Sans ça, l'agent ignore quels fichiers existent : search_kb est une
    recherche par contenu (pas un listing) et run_code tourne dans un sandbox
    isolé. L'inventaire est borné par `cap`.
    """
    if not documents:
        return t(locale, "tools.inventory_empty")
    lines: list[str] = []
    for doc in documents[:cap]:
        path = doc.metadata.get("relativePath") or doc.id
        kind = doc.metadata.get("kind") or t(locale, "tools.inventory_kind_file")
        lines.append(f"- {path} ({kind})")
    text = t(locale, "tools.inventory_header") + "\n" + "\n".join(lines)
    if len(documents) > cap:
        text += "\n" + t(
            locale,
            "tools.inventory_overflow",
            count=len(documents) - cap,
        )
    text += t(locale, "tools.inventory_footer")
    return text


def _truncate_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "..."


def _session_extract(messages: Any, locale: str = DEFAULT_LOCALE) -> str:
    if not isinstance(messages, list):
        return ""

    first_user = ""
    last_assistant = ""
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        if role == "user" and not first_user:
            first_user = _truncate_text(content.strip(), 200)
        elif role == "assistant":
            last_assistant = _truncate_text(content.strip(), 300)

    parts: list[str] = []
    if first_user:
        parts.append(t(locale, "tools.session_first_request", text=first_user))
    if last_assistant:
        parts.append(t(locale, "tools.session_last_reply", text=last_assistant))
    return "\n".join(parts)


def build_session_digests(
    data_dir: Path,
    current_session_id: str,
    query: str = "",
    locale: str = DEFAULT_LOCALE,
) -> dict[str, Any]:
    conv_dir = data_dir / "conversations"
    if not conv_dir.is_dir():
        return {"sessions": [], "count": 0}

    sessions: list[dict[str, Any]] = []
    for session_path in conv_dir.glob("*.json"):
        try:
            with session_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue

        session_id = data.get("id")
        if session_id == current_session_id:
            continue

        title = data.get("title") or "Conversation"
        summary_value = data.get("summary")
        summary = summary_value.strip() if isinstance(summary_value, str) else ""
        extract = "" if summary else _session_extract(data.get("messages"), locale)
        sessions.append(
            {
                "id": session_id,
                "title": title,
                "summary": summary or extract,
                "createdAt": data.get("createdAt"),
                "updatedAt": data.get("updatedAt"),
            }
        )

    sessions.sort(key=lambda session: session.get("updatedAt") or "", reverse=True)
    total_available = len(sessions)

    keywords = [keyword.lower() for keyword in query.split() if keyword.strip()]
    if keywords:
        sessions = [
            session
            for session in sessions
            if any(
                keyword
                in f"{session.get('title') or ''} {session.get('summary') or ''}".lower()
                for keyword in keywords
            )
        ]

    returned = sessions[:20]
    return {
        "sessions": returned,
        "count": len(returned),
        "total_available": total_available,
    }


def build_agent(
    model: Any,
    *,
    ui_mode: UiMode = "guided",
    sandbox_available: bool = True,
    locale: str = DEFAULT_LOCALE,
    active_plugins: list[str] | None = None,
) -> Agent[ToolDeps, str]:
    """Construit l'agent Pydantic AI avec ses outils métier."""
    agent: Agent[ToolDeps, str] = Agent(
        model=model,
        deps_type=ToolDeps,
        output_type=str,
        system_prompt=system_prompt_for_locale(locale),
    )

    @agent.system_prompt
    def project_inventory_prompt(ctx: RunContext[ToolDeps]) -> str:
        """Injecte l'inventaire des fichiers projet reçus dans le payload."""
        return build_inventory_prompt(
            ctx.deps.context.documents,
            ctx.deps.limits.inventory_max_entries,
            locale=ctx.deps.context.locale,
        )

    @agent.system_prompt
    def project_sessions_prompt(ctx: RunContext[ToolDeps]) -> str:
        data_dir = ctx.deps.context.workspace_data_dir
        if data_dir is None:
            return ""
        conv_dir = data_dir / "conversations"
        if not conv_dir.is_dir():
            return ""
        try:
            others = sum(
                1
                for p in conv_dir.glob("*.json")
                if p.stem != ctx.deps.context.session_id
            )
        except Exception:
            return ""
        if others == 0:
            return ""
        return t(
            ctx.deps.context.locale,
            "tools.sessions_note",
            count=others,
        )

    @agent.system_prompt
    def plan_mode_instruction(ctx: RunContext[ToolDeps]) -> str:
        return t(ctx.deps.context.locale, "tools.plan_mode_prompt")

    @agent.system_prompt
    def memory_prompt(ctx: RunContext[ToolDeps]) -> str:
        """Injecte les souvenirs explicites user (global) + project (espace).

        Cohérence : l'agent connaît en permanence les faits mémorisés à chaque
        niveau, sans outil de lecture explicite. La persistance est assurée par
        deux bases SQLite distinctes ouvertes sans embeddings (souvenirs only).
        """
        from app.memory_stores import open_memory_store_for_scope

        data_dir = ctx.deps.context.workspace_data_dir
        locale = ctx.deps.context.locale
        if data_dir is None:
            return ""

        def _format(scope: str, header_key: str) -> str:
            try:
                store = open_memory_store_for_scope(scope, data_dir)
            except Exception:
                return ""
            try:
                items = store.list_memories()
            finally:
                store.close()
            if not items:
                return ""
            lines = [t(locale, header_key)]
            for item in items[:64]:
                content = str(item.get("content", "")).strip().replace("\n", " ")
                if not content:
                    continue
                lines.append(f"- {content}")
            return "\n".join(lines)

        user_block = _format("user", "memory.agent_user_header")
        project_block = _format("project", "memory.agent_project_header")
        if not user_block and not project_block:
            return ""
        return f"{user_block}\n{project_block}".strip()

    @agent.tool
    async def remember(
        ctx: RunContext[ToolDeps],
        content: str,
        scope: Literal["user", "project"] = "project",
    ) -> dict[str, Any]:
        """Persist a factual memory so it is available in future turns.

        Use this when the user shares a durable fact or preference worth keeping
        across conversations. Choose `scope`:
        - "user" for facts about the user that apply to ALL spaces (preferences,
          identity, recurring context).
        - "project" for facts specific to the current workspace.
        Keep entries short, factual and self-contained. Avoid storing transient
        information already present in files or conversation history.

        Args:
            content: The memory to store, as a concise factual sentence.
            scope: "user" (global) or "project" (this space). Defaults to project.
        """
        from app.memory_stores import open_memory_store_for_scope

        data_dir = ctx.deps.context.workspace_data_dir
        if data_dir is None:
            return {"ok": False, "error": "no_workspace"}
        try:
            store = open_memory_store_for_scope(scope, data_dir)
        except Exception as exc:  # noqa: BLE001 - surfaced to the model
            raise _retry(exc) from exc
        try:
            memory = store.add_memory(content=content, source="agent")
        except ValueError as exc:
            raise _retry(exc) from exc
        finally:
            store.close()
        return {"ok": True, "memory": memory, "scope": scope}

    @agent.tool
    async def propose_plan(
        ctx: RunContext[ToolDeps],
        steps: list[dict[str, Any]],
        rationale: str,
    ) -> dict[str, Any]:
        """Propose an execution plan for user approval before complex work.

        Call this when the task touches multiple files, requires three or more
        tool steps, involves destructive changes, or the user explicitly asks
        for a plan. Each step should include `tool`, `summary`, and optional
        `target` (file path). Wait for approval before proceeding with writes.

        Args:
            steps: Planned steps as dicts with tool, summary, and optional target.
            rationale: Short explanation of why this plan is needed.
        """
        gate = ctx.deps.plan_gate
        if gate is None:
            return {"skipped": True, "steps": steps, "rationale": rationale}
        try:
            return await gate.request_plan(
                steps=steps,
                rationale=rationale,
                locale=ctx.deps.context.locale,
            )
        except Exception as exc:  # noqa: BLE001
            raise _retry(exc) from exc

    @agent.tool
    async def list_files(
        ctx: RunContext[ToolDeps],
        subdir: str = "",
        max_entries: int = 200,
    ) -> dict[str, Any]:
        """List project files and folders under an optional subdirectory.

        Returns a bounded tree (respecting ignored dirs like `.git`,
        `node_modules`). Use this to answer "what's in the folder?" or to
        discover file names before reading them. `subdir` is a relative path
        within the project (defaults to the project root).

        Args:
            subdir: Optional relative subdirectory to list (defaults to root).
            max_entries: Max entries to return. Clamped server-side.
        """
        deps = ctx.deps
        try:
            response = await deps.project_client.list_files(
                subdir=subdir,
                max_entries=max_entries,
            )
            return response.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001 - surfaced to the model
            raise _retry(exc) from exc

    @agent.tool
    async def recall_project_sessions(
        ctx: RunContext[ToolDeps],
        query: str = "",
    ) -> dict[str, Any]:
        """List other conversations in this project with a short summary of each.

        Returns the prior conversations of the current project (excluding the
        active one), most recent first, with for each: id, title, createdAt,
        updatedAt, and a `summary` (the persisted summary if available, otherwise
        an extract of the first user message and the last assistant reply). Use
        this to recall what was discussed or produced in earlier sessions on the
        same dossier before re-asking the user. Pass `query` to filter by keywords
        (matched against title + summary, case-insensitive).

        Args:
            query: Optional keywords to filter sessions (title + summary match).
        """
        data_dir = ctx.deps.context.workspace_data_dir
        if data_dir is None:
            return {
                "sessions": [],
                "count": 0,
                "note": t(ctx.deps.context.locale, "tools.sessions_no_folder"),
            }
        try:
            return build_session_digests(
                data_dir=data_dir,
                current_session_id=ctx.deps.context.session_id,
                query=query,
                locale=ctx.deps.context.locale,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the model
            raise _retry(exc) from exc

    @agent.tool
    async def search_kb(
        ctx: RunContext[ToolDeps],
        query: str,
        limit: int = 8,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Search the current project knowledge base or local files.

        Recherche par mot-clé dans le contenu ET dans les noms de fichiers du
        projet. Transmets tels quels les termes littéraux de l'utilisateur,
        y compris un nom de fichier s'il en cite un (ex. « mémoire collective »
        ou « rapport-q3.md »). N'utilise PAS d'opérateurs booléens (OR, AND,
        |) : le serveur découpe la requête en mots-clés et matche chacun
        indépendamment. Si la première requête ne donne rien, reformule avec
        les mots-clés exacts présents dans le fichier recherché plutôt qu'avec
        des synonymes.

        Args:
            query: The search query (natural language or keywords).
            limit: Maximum number of results to return. Clamped to 1..20 by the server.
            filters: Optional metadata filters.
        """
        deps = ctx.deps
        clamped = max(1, min(int(limit), deps.limits.search_max_limit))
        try:
            response = await deps.project_client.search_kb(
                tenant_id=deps.context.tenant_id,
                project_id=deps.context.project_id,
                query=query,
                limit=clamped,
                filters=filters,
            )
            return response.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001 - surfaced to the model
            raise _retry(exc) from exc

    @agent.tool
    async def read_document(
        ctx: RunContext[ToolDeps],
        document_id: str,
        offset_lines: int = 0,
        max_lines: int = 0,
    ) -> dict[str, Any]:
        """Read a project document by id or relative local path.

        Reads a bounded window of the file (the server caps the number of lines
        and bytes returned). For text files, use `offset_lines` to paginate when
        the result is `truncated`. For binary documents (PDF, docx, xlsx, pptx),
        pagination params are ignored and extraction is capped server-side.

        Args:
            document_id: Relative path or id of the document within the project.
            offset_lines: Number of lines to skip from the top (text files only).
            max_lines: Max lines to return. 0 = server default (capped).
        """
        deps = ctx.deps
        try:
            document = await deps.project_client.read_document(
                tenant_id=deps.context.tenant_id,
                project_id=deps.context.project_id,
                document_id=document_id,
                offset_lines=offset_lines,
                max_lines=max_lines,
            )
            return document.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001 - surfaced to the model
            raise _retry(exc) from exc

    if ui_mode == "advanced":

        @agent.tool
        async def run_code(
            ctx: RunContext[ToolDeps],
            code: str,
            project_files: list[str] | None = None,
        ) -> dict[str, Any]:
            """Run generated Python code in the isolated sandbox.

            The sandbox runs in a throwaway working directory with resource limits
            (CPU, memory, file size) and a minimal environment. Only the files listed
            in `project_files` (relative paths within the project) are copied in and
            made available to the code; writes stay inside the sandbox and are
            returned in `files`. Network access is blocked when possible.

            Args:
                code: Python source code to execute.
                project_files: Optional list of project file paths to make available.
            """
            deps = ctx.deps
            if deps.context.settings_locked and not deps.context.code_execute:
                raise ModelRetry(t(deps.context.locale, "errors.code_execute_locked"))
            if not sandbox_available:
                raise ModelRetry(t(ctx.deps.context.locale, "tools.sandbox_unavailable"))
            project_root = deps.context.project_root
            try:
                result = await deps.sandbox_runner.run(
                    code=code,
                    project_files=list(project_files or []),
                    project_root=project_root,
                )
                return result.model_dump(mode="json")
            except Exception as exc:  # noqa: BLE001 - surfaced to the model
                raise _retry(exc) from exc

    async def _persist_binary_document(
        ctx: RunContext[ToolDeps],
        *,
        tool_name: str,
        name: str,
        mime_type: str,
        content: bytes,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        deps = ctx.deps
        proposed_path, action = _write_action(deps.context.project_root, name)
        gate = deps.confirmation_gate

        if gate is not None:
            human_summary = build_human_summary(
                tool_name,
                {"name": name},
                locale=deps.context.locale,
            )
            approved = await gate.request_write(
                tool_call_id=ctx.tool_call_id or "",
                tool_name=tool_name,
                action=action,
                proposed_path=proposed_path,
                human_summary=human_summary,
            )
            if not approved:
                return {
                    "cancelled": True,
                    "message": t(
                        deps.context.locale,
                        "tools.action_cancelled_by_user",
                    ),
                }

        content_base64 = base64.b64encode(content).decode("ascii")
        try:
            document = await deps.project_client.save_generated_document(
                tenant_id=deps.context.tenant_id,
                project_id=deps.context.project_id,
                session_id=deps.context.session_id,
                name=name,
                mime_type=mime_type,
                content_base64=content_base64,
                metadata={"generated_by": "workproba-ai", **(metadata or {})},
            )
            return document.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001 - surfaced to the model
            raise _retry(exc) from exc

    @agent.tool
    async def generate_document(
        ctx: RunContext[ToolDeps],
        name: str,
        mime_type: str,
        content_markdown: str,
    ) -> dict[str, Any]:
        """Save a generated document into the project.

        Args:
            name: Relative path/name of the document to create.
            mime_type: MIME type of the document (e.g. text/markdown).
            content_markdown: The markdown content to write.
        """
        return await _persist_binary_document(
            ctx,
            tool_name="generate_document",
            name=name,
            mime_type=mime_type,
            content=content_markdown.encode("utf-8"),
        )

    @agent.tool
    async def write_docx(
        ctx: RunContext[ToolDeps],
        path: str,
        title: str = "",
        paragraphs: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a native Word (.docx) file in the workspace.

        Args:
            path: Relative path for the .docx file.
            title: Optional document title (heading).
            paragraphs: Body paragraphs to include.
        """
        try:
            content = build_docx_bytes(title=title or None, paragraphs=paragraphs)
        except Exception as exc:  # noqa: BLE001
            raise _retry(exc) from exc
        return await _persist_binary_document(
            ctx,
            tool_name="write_docx",
            name=path,
            mime_type=(
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document"
            ),
            content=content,
            metadata={"format": "docx"},
        )

    @agent.tool
    async def write_xlsx(
        ctx: RunContext[ToolDeps],
        path: str,
        sheets: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create a native Excel (.xlsx) file in the workspace.

        Args:
            path: Relative path for the .xlsx file.
            sheets: Sheet definitions with `name` and `rows` (list of row arrays).
        """
        try:
            content = build_xlsx_bytes(sheets=sheets)
        except Exception as exc:  # noqa: BLE001
            raise _retry(exc) from exc
        return await _persist_binary_document(
            ctx,
            tool_name="write_xlsx",
            name=path,
            mime_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            content=content,
            metadata={"format": "xlsx"},
        )

    @agent.tool
    async def write_pdf(
        ctx: RunContext[ToolDeps],
        path: str,
        title: str = "",
        sections: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create a native PDF file in the workspace (ReportLab).

        Args:
            path: Relative path for the .pdf file.
            title: Optional document title.
            sections: Sections with optional `heading` and `body` text.
        """
        try:
            content = build_pdf_bytes(title=title or None, sections=sections)
        except RuntimeError as exc:
            raise ModelRetry(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise _retry(exc) from exc
        return await _persist_binary_document(
            ctx,
            tool_name="write_pdf",
            name=path,
            mime_type="application/pdf",
            content=content,
            metadata={"format": "pdf"},
        )

    from app.plugins.registry import register_plugin_tools

    register_plugin_tools(agent, active_plugins=active_plugins)

    return agent


__all__ = [
    "ToolContext",
    "ToolDeps",
    "build_agent",
    "build_inventory_prompt",
    "build_session_digests",
    "system_prompt_for_locale",
    "WORKPROBA_SYSTEM_PROMPT",
]
