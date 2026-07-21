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

from app.agent.confirmation import ConfirmationGate, raise_unless_approved
from app.agent.effects import classify_effect, effect_headline, protection_labels
from app.agent.human import build_human_summary
from app.agent.plan import PlanGate
from app.documents.writer import (
    build_docx_bytes,
    build_pdf_bytes,
    build_pdf_bytes_from_slides,
    build_pptx_bytes,
    build_xlsx_bytes,
    require_path_extension,
)
from app.i18n import DEFAULT_LOCALE, t
from app.limits import DEFAULT_LIMITS, Limits
from app.project_client import ProjectClient
from app.web_search import (
    WebSearchError,
    search_web,
    web_search_available,
    web_search_error_detail,
)

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
    workspace_title: str | None = None
    locale: str = DEFAULT_LOCALE
    active_plugins: list[str] | None = None
    plugin_data_dir: Path | None = None
    provider_set: ProviderSet | None = None
    settings_locked: bool = False
    permissions_network: bool = True
    code_execute: bool = True
    audit_retention_days: int | None = None
    audit_enabled: bool | None = None
    browser_pilotage_paused: bool = False
    last_user_query: str = ""
    work_id: str | None = None
    memory_query_embedding: tuple[float, ...] | None = None
    memory_item_embeddings: dict[str, tuple[float, ...]] | None = None
    session_item_embeddings: dict[str, tuple[float, ...]] | None = None
    prepared_session_candidates: tuple[dict, ...] | None = None
    prepared_tagged_memories: tuple[dict, ...] | None = None
    ui_mode: str = "guided"


@dataclass
class ToolDeps:
    context: ToolContext
    project_client: ProjectClient
    sandbox_runner: SandboxRunner
    limits: Limits = field(default_factory=lambda: DEFAULT_LIMITS)
    confirmation_gate: ConfirmationGate | None = None
    plan_gate: PlanGate | None = None
    web_search_calls: int = 0


def _retry(exc: Exception) -> ModelRetry:
    return ModelRetry(f"{type(exc).__name__}: {exc}")


def select_memories_for_injection(
    *,
    workspace_data_dir: Path | None,
    query: str,
    prepared_tagged_memories: tuple[dict, ...] | list[dict] | None = None,
    memory_query_embedding: tuple[float, ...] | None = None,
    memory_item_embeddings: dict[str, tuple[float, ...]] | None = None,
) -> list[dict]:
    """Sélectionne les souvenirs injectés dans le prompt agent (ordre d'injection)."""
    from app.agent.memory_ranking import (
        dedupe_memories_keep_order,
        rank_memories_hybrid,
    )
    from app.config import get_settings

    if workspace_data_dir is None:
        return []

    settings = get_settings()
    topk = settings.memory_prompt_topk
    recent_floor = settings.memory_prompt_recent_floor

    if prepared_tagged_memories is not None:
        tagged = list(prepared_tagged_memories)
    else:
        from app.memory_stores import open_memory_store_for_scope

        def _collect(scope: str) -> list[dict]:
            try:
                store = open_memory_store_for_scope(scope, workspace_data_dir)
            except Exception:
                return []
            try:
                return [{**item, "_scope": scope} for item in store.list_memories()]
            finally:
                store.close()

        tagged = dedupe_memories_keep_order(_collect("user") + _collect("project"))

    if not tagged:
        return []

    chronological = list(reversed(tagged))
    recent = chronological[-recent_floor:] if recent_floor > 0 else []
    remaining_k = max(0, topk - len(recent))
    ranked = rank_memories_hybrid(
        chronological,
        query,
        remaining_k,
        query_embedding=memory_query_embedding,
        item_embeddings=memory_item_embeddings,
        semantic_weight=settings.memory_ranking_semantic_weight,
        min_semantic_score=settings.memory_ranking_min_semantic_score,
    )
    recent_keys = {
        str(item.get("content", "")).strip().lower() for item in recent
    }
    selected = recent + [
        item
        for item in ranked
        if str(item.get("content", "")).strip().lower() not in recent_keys
    ]
    return selected[:topk]


def memory_citations_from_items(items: list[dict], *, snippet_len: int = 120) -> list[dict]:
    """Formate les souvenirs sélectionnés pour l'UI (citations cliquables)."""
    citations: list[dict] = []
    for item in items:
        content = str(item.get("content", "")).strip().replace("\n", " ")
        if not content:
            continue
        memory_id = str(item.get("id") or item.get("memory_id") or "")
        if not memory_id:
            continue
        snippet = content if len(content) <= snippet_len else f"{content[: snippet_len - 1]}…"
        citations.append(
            {
                "id": memory_id,
                "snippet": snippet,
                "source": str(item.get("source") or ""),
                "scope": str(item.get("_scope") or "project"),
            }
        )
    return citations


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
        if session_id == current_session_id or session_path.stem == current_session_id:
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


def filter_rankable_sessions(
    sessions: list[dict],
    workspace_data_dir: Path,
) -> list[dict]:
    """Exclut les sessions dont les faits ont déjà été promus en mémoire projet."""
    from app.agent.memory_consolidation import session_has_promoted_facts
    from app.memory_stores import open_memory_store_for_scope

    if not sessions:
        return []

    project_store = open_memory_store_for_scope("project", workspace_data_dir)
    try:
        return [
            session
            for session in sessions
            if not session_has_promoted_facts(
                project_store,
                str(session.get("id") or ""),
            )
        ]
    finally:
        project_store.close()


def build_agent(
    model: Any,
    *,
    ui_mode: UiMode = "guided",
    sandbox_available: bool = True,
    locale: str = DEFAULT_LOCALE,
    active_plugins: list[str] | None = None,
    plugin_data_dir: Path | None = None,
) -> Agent[ToolDeps, str]:
    """Construit l'agent Pydantic AI avec ses outils métier."""
    agent: Agent[ToolDeps, str] = Agent(
        model=model,
        deps_type=ToolDeps,
        output_type=str,
        system_prompt=system_prompt_for_locale(locale),
    )

    # Refs audit : app.prompts.registry.DYNAMIC_HOOK_SPECS
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
    def relevant_sessions_prompt(ctx: RunContext[ToolDeps]) -> str:
        """Injecte les résumés d'autres sessions pertinentes pour la requête courante."""
        from app.agent.memory_ranking import rank_sessions_hybrid
        from app.agent.untrusted import wrap_untrusted_content
        from app.config import get_settings

        data_dir = ctx.deps.context.workspace_data_dir
        locale = ctx.deps.context.locale
        query = (ctx.deps.context.last_user_query or "").strip()
        if data_dir is None or not query:
            return ""

        settings = get_settings()
        topk = settings.memory_proactive_sessions_topk
        min_overlap = settings.memory_proactive_sessions_min_overlap
        if topk <= 0:
            return ""

        try:
            if ctx.deps.context.prepared_session_candidates is not None:
                sessions = list(ctx.deps.context.prepared_session_candidates)
            else:
                digest = build_session_digests(
                    data_dir=data_dir,
                    current_session_id=ctx.deps.context.session_id,
                    locale=locale,
                )
                sessions = digest.get("sessions") or []
                if not isinstance(sessions, list) or not sessions:
                    return ""
                sessions = filter_rankable_sessions(sessions, data_dir)
        except Exception:
            return ""

        if not sessions:
            return ""

        relevant = rank_sessions_hybrid(
            sessions,
            query,
            topk,
            query_embedding=ctx.deps.context.memory_query_embedding,
            session_embeddings=ctx.deps.context.session_item_embeddings,
            semantic_weight=settings.memory_ranking_semantic_weight,
            min_semantic_score=settings.memory_ranking_min_semantic_score,
            min_overlap=min_overlap,
        )
        if not relevant:
            return ""

        lines: list[str] = []
        for session in relevant:
            title = str(session.get("title") or "Conversation").strip()
            summary = str(session.get("summary") or "").strip().replace("\n", " ")
            if not summary:
                continue
            lines.append(
                t(
                    locale,
                    "memory.relevant_session_entry",
                    title=title,
                    summary=summary[:400],
                )
            )
        if not lines:
            return ""

        wrapped = wrap_untrusted_content(
            "\n".join(lines),
            locale,
            "memory.untrusted_header",
        )
        guardrail = t(locale, "memory.agent_guardrail")
        header = t(locale, "memory.relevant_sessions_header")
        return f"{guardrail}\n\n{header}\n{wrapped}"

    @agent.system_prompt
    def space_name_prompt(ctx: RunContext[ToolDeps]) -> str:
        title = ctx.deps.context.workspace_title
        if not title or not title.strip():
            return ""
        return t(
            ctx.deps.context.locale,
            "tools.space_name_context",
            name=title.strip(),
        )

    @agent.system_prompt
    def web_search_note_prompt(ctx: RunContext[ToolDeps]) -> str:
        if not web_search_available(ctx.deps.context):
            return ""
        return t(ctx.deps.context.locale, "tools.web_search_note")

    @agent.system_prompt
    def plan_mode_instruction(ctx: RunContext[ToolDeps]) -> str:
        return t(ctx.deps.context.locale, "tools.plan_mode_prompt")

    @agent.system_prompt
    def approval_gate_instruction(ctx: RunContext[ToolDeps]) -> str:
        return t(ctx.deps.context.locale, "tools.approval_gate_prompt")

    @agent.system_prompt
    def memory_prompt(ctx: RunContext[ToolDeps]) -> str:
        """Injecte les souvenirs explicites user (global) + project (espace).

        Cohérence : l'agent connaît en permanence les faits mémorisés à chaque
        niveau, sans outil de lecture explicite. La persistance est assurée par
        deux bases SQLite distinctes ouvertes sans embeddings (souvenirs only).
        """
        from app.config import get_settings

        data_dir = ctx.deps.context.workspace_data_dir
        locale = ctx.deps.context.locale
        if data_dir is None:
            return ""

        settings = get_settings()
        selected = select_memories_for_injection(
            workspace_data_dir=data_dir,
            query=ctx.deps.context.last_user_query,
            prepared_tagged_memories=ctx.deps.context.prepared_tagged_memories,
            memory_query_embedding=ctx.deps.context.memory_query_embedding,
            memory_item_embeddings=ctx.deps.context.memory_item_embeddings,
        )
        if not selected:
            return ""

        from app.agent.untrusted import wrap_untrusted_content

        def _format(header_key: str, scope: str) -> str:
            scope_items = [item for item in selected if item.get("_scope") == scope]
            if not scope_items:
                return ""
            bullets: list[str] = []
            for item in scope_items:
                content = str(item.get("content", "")).strip().replace("\n", " ")
                if not content:
                    continue
                bullets.append(f"- {content}")
            if not bullets:
                return ""
            wrapped = wrap_untrusted_content(
                "\n".join(bullets),
                locale,
                "memory.untrusted_header",
            )
            return f"{t(locale, header_key)}\n{wrapped}"

        user_block = _format("memory.agent_user_header", "user")
        project_block = _format("memory.agent_project_header", "project")
        blocks = [block for block in (user_block, project_block) if block]
        if not blocks:
            return ""
        guardrail = t(locale, "memory.agent_guardrail")
        return f"{guardrail}\n\n" + "\n\n".join(blocks)

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
        from app.agent.memory_consolidation import apply_explicit_memory_heuristic
        from app.config import get_settings
        from app.memory_stores import open_memory_store_for_scope

        data_dir = ctx.deps.context.workspace_data_dir
        if data_dir is None:
            return {"ok": False, "error": "no_workspace"}
        settings = get_settings()
        try:
            store = open_memory_store_for_scope(scope, data_dir)
        except Exception as exc:  # noqa: BLE001 - surfaced to the model
            raise _retry(exc) from exc
        try:
            memory, operation = apply_explicit_memory_heuristic(
                store,
                content,
                source="agent",
                update_threshold=settings.memory_promotion_overlap_threshold,
            )
            if scope == "project" and settings.memory_project_max_entries > 0:
                store.trim_memories_to_cap(
                    settings.memory_project_max_entries,
                    actor="system",
                )
        except ValueError as exc:
            raise _retry(exc) from exc
        finally:
            store.close()
        return {
            "ok": True,
            "memory": memory,
            "scope": scope,
            "operation": operation,
        }

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
    async def web_search(ctx: RunContext[ToolDeps], query: str) -> dict[str, Any]:
        """Search the public web for up-to-date information.

        Use when the user asks about recent events, prices, news, or external
        facts not available in project files or space memory. Do NOT use for
        local project content (use search_kb instead).

        Args:
            query: Natural-language search query reflecting the user's topic.
        """
        locale = ctx.deps.context.locale
        if not ctx.deps.context.permissions_network:
            raise ModelRetry(web_search_error_detail("web_search_locked", locale))
        if not web_search_available(ctx.deps.context):
            raise ModelRetry(web_search_error_detail("web_search_unavailable", locale))
        if ctx.deps.web_search_calls >= ctx.deps.limits.web_search_max_per_turn:
            raise ModelRetry(t(locale, "errors.web_search_limit_reached"))

        try:
            result = await search_web(
                query,
                provider_set=ctx.deps.context.provider_set,
                locale=locale,
                limits=ctx.deps.limits,
            )
        except WebSearchError as exc:
            raise ModelRetry(web_search_error_detail(str(exc), locale)) from exc
        except Exception as exc:  # noqa: BLE001
            raise _retry(exc) from exc

        ctx.deps.web_search_calls += 1
        if ctx.deps.context.plugin_data_dir is not None:
            from app.agent.work_events import audit_details_with_work_id
            from app.audit import log_event, resolve_app_data_dir

            log_event(
                resolve_app_data_dir(ctx.deps.context.plugin_data_dir),
                "web_search.query",
                "agent",
                audit_details_with_work_id(
                    {
                        "query": result.get("query", query),
                        "backend": result.get("backend"),
                        "count": result.get("count", 0),
                    },
                    ctx.deps.context.work_id,
                    session_id=ctx.deps.context.session_id,
                ),
                enabled=ctx.deps.context.audit_enabled,
            )
        return result

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
        gate = deps.confirmation_gate

        if gate is not None:
            human_summary = build_human_summary(
                tool_name,
                {"name": name},
                locale=deps.context.locale,
            )
            proposal = classify_effect(
                tool_name,
                {"name": name, "project_root": deps.context.project_root},
                permissions_network=deps.context.permissions_network,
            )
            if proposal is None:
                raise ModelRetry(
                    f"Effet non classifiable pour l'outil d'écriture {tool_name}"
                )
            proposal = proposal.model_copy(update={"human_summary": human_summary})
            locale = deps.context.locale
            proposal = proposal.model_copy(
                update={
                    "headline": effect_headline(proposal, locale),
                    "protection_labels": protection_labels(proposal, locale),
                }
            )
            outcome = await gate.request_effect(
                tool_call_id=ctx.tool_call_id or "",
                proposal=proposal,
                audit_app_data_dir=deps.context.workspace_data_dir,
                audit_enabled=deps.context.audit_enabled,
            )
            raise_unless_approved(outcome, deps.context.locale)

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

    _NATIVE_OFFICE_EXTS = frozenset({".docx", ".xlsx", ".pptx", ".pdf"})

    @agent.tool
    async def generate_document(
        ctx: RunContext[ToolDeps],
        name: str,
        mime_type: str,
        content_markdown: str,
    ) -> dict[str, Any]:
        """Save a generated markdown/text document into the project.

        Do not use for Office binaries: use write_docx, write_xlsx, write_pptx,
        or write_pdf instead (path extension must match the real format).

        Args:
            name: Relative path/name of the document to create.
            mime_type: MIME type of the document (e.g. text/markdown).
            content_markdown: The markdown content to write.
        """
        from pathlib import Path as _Path

        suffix = _Path(name).suffix.lower()
        if suffix in _NATIVE_OFFICE_EXTS:
            raise ModelRetry(
                "Pour un fichier Office/PDF natif, utilise write_docx, "
                "write_xlsx, write_pptx ou write_pdf (jamais generate_document "
                f"avec l'extension {suffix})."
            )
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
            path: Relative path for the .docx file (must end with .docx).
            title: Optional document title (heading).
            paragraphs: Body paragraphs to include.
        """
        try:
            require_path_extension(path, ".docx")
            content = build_docx_bytes(title=title or None, paragraphs=paragraphs)
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc
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
            path: Relative path for the .xlsx file (must end with .xlsx).
            sheets: Sheet definitions with `name` and `rows` (list of row arrays).
        """
        try:
            require_path_extension(path, ".xlsx")
            content = build_xlsx_bytes(sheets=sheets)
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc
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
    async def write_pptx(
        ctx: RunContext[ToolDeps],
        path: str,
        slides: list[dict[str, Any]] | None = None,
        theme: str = "improba",
        fidelity: str = "editable",
    ) -> dict[str, Any]:
        """Create a native PowerPoint (.pptx) presentation in the workspace.

        Use this whenever the user asks for a .pptx / PowerPoint / présentation
        éditable. Never write Word or markdown under a .pptx name.

        Each slide is a dict with either:
        - grammar (hero | split | comparison | sequence | dashboard | diagram | editorial)
          + hierarchy {primary, secondary[], tertiary[]} + visual {type, items[]}
        - or legacy layout (title | section | bullets | two_column | kpi_row | quote | closing)
          + title, subtitle, bullets, left, right, metrics, quote, etc.

        Args:
            path: Relative path ending with .pptx.
            slides: Structured slide definitions.
            theme: Visual theme: improba (default), light, or dark.
            fidelity: editable (native shapes) or visual (HTML screenshot, repli éditable sans Chromium).
        """
        fidelity_key = (fidelity or "editable").strip().lower()
        metadata: dict[str, Any] = {
            "format": "pptx",
            "theme": theme or "improba",
            "fidelity": fidelity_key,
        }
        try:
            require_path_extension(path, ".pptx")
            if fidelity_key == "visual":
                from app.documents.pptx_svg import build_pptx_visual_bytes

                content, render_meta = build_pptx_visual_bytes(slides, theme=theme)
                metadata.update(render_meta)
            else:
                from app.documents.pptx_builder import build_pptx_editable_bytes
                from app.documents.slides_critique import critique_and_fix

                critique = critique_and_fix(slides, theme=theme)
                content, _ = build_pptx_editable_bytes(
                    slides=critique.slides, theme=theme, skip_critique=True
                )
                metadata["critique_issues"] = len(critique.issues)
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise _retry(exc) from exc
        return await _persist_binary_document(
            ctx,
            tool_name="write_pptx",
            name=path,
            mime_type=(
                "application/vnd.openxmlformats-officedocument"
                ".presentationml.presentation"
            ),
            content=content,
            metadata=metadata,
        )

    @agent.tool
    async def write_pdf(
        ctx: RunContext[ToolDeps],
        path: str,
        title: str = "",
        sections: list[dict[str, Any]] | None = None,
        slides: list[dict[str, Any]] | None = None,
        theme: str = "improba",
    ) -> dict[str, Any]:
        """Create a native PDF file in the workspace.

        Use ``sections`` for a simple ReportLab document, or ``slides`` for a
        deck PDF (Chromium HTML render when available, else ReportLab fallback).

        Args:
            path: Relative path for the .pdf file (must end with .pdf).
            title: Optional document title (sections mode).
            sections: Sections with optional `heading` and `body` text.
            slides: Optional semantic slides (same schema as write_pptx).
            theme: Theme for slides PDF rendering (improba, light, dark).
        """
        try:
            require_path_extension(path, ".pdf")
            if slides is not None:
                content = build_pdf_bytes_from_slides(slides=slides, theme=theme)
                metadata: dict[str, Any] = {
                    "format": "pdf",
                    "source": "slides",
                    "theme": theme or "improba",
                }
            else:
                content = build_pdf_bytes(title=title or None, sections=sections)
                metadata = {"format": "pdf", "source": "sections"}
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc
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
            metadata=metadata,
        )

    from app.plugins.registry import register_plugin_tools

    register_plugin_tools(
        agent,
        active_plugins=active_plugins,
        plugin_data_dir=plugin_data_dir,
        ui_mode=ui_mode,
    )

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
