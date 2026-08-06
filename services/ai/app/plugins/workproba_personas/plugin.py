"""Outils agent du plugin personas."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ModelRetry

from app.agent.human import build_human_summary
from app.config import get_settings
from app.i18n import t
from app.agent.tools import ToolDeps
from app.plugins.registry import PLUGIN_WORKPROBA_PERSONAS, resolve_plugin_data_dir
from app.plugins.workproba_personas import manifest, orchestrator, specialist_run, storage
from app.plugins.workproba_personas.delegation_prompt import (
    build_business_agents_delegation_prompt,
)
from app.plugins.workproba_personas.storage import JsonDict

SpecialistDelegationMode = Literal["regard", "operative"]


def _plugin_data_dir(ctx: RunContext[Any]) -> Path:
    data_dir = resolve_plugin_data_dir(
        PLUGIN_WORKPROBA_PERSONAS,
        ctx.deps.context.plugin_data_dir,
    )
    if data_dir is None:
        raise ModelRetry("Plugin personas: plugin_data_dir manquant")
    return data_dir


def _persona_label(personas: list[JsonDict]) -> str:
    return ", ".join(str(p.get("name") or p.get("id") or "") for p in personas)


def _normalize_specialist_mode(mode: str, *, locale: str) -> SpecialistDelegationMode:
    normalized = (mode or "regard").strip().lower()
    if normalized in {"regard", "operative"}:
        return normalized  # type: ignore[return-value]
    raise ModelRetry(t(locale, "errors.invalid_specialist_mode", mode=mode))


def _available_specialist_ids(managed: list[JsonDict], *, limit: int = 12) -> str:
    ids = sorted(
        str(specialist.get("id") or "")
        for specialist in managed
        if specialist.get("id")
    )
    return ", ".join(ids[:limit])


def _summon_specialist_failure_result(
    *,
    specialist_id: str,
    mode: SpecialistDelegationMode,
    locale: str,
    error_code: str,
    content: str,
    task: str,
) -> dict[str, Any]:
    name = specialist_id
    return {
        "specialist_id": specialist_id,
        "specialist_name": name,
        "mode": mode,
        "content": content,
        "degraded_tools": [],
        "error": error_code,
        "display": "specialist_handoff_card",
        "human_summary": build_human_summary(
            "summon_specialist",
            {"specialist_id": specialist_id, "name": name, "mode": mode, "task": task},
            result={"error": error_code},
            is_error=True,
            locale=locale,
        ),
    }


def _resolve_specialist_for_summon(
    plugin_data_dir: Path,
    specialist_id: str,
    *,
    locale: str,
) -> JsonDict:
    specialists = storage.resolve_specialists(plugin_data_dir, [specialist_id])
    if specialists:
        return specialists[0]

    managed = storage.list_managed_specialists(plugin_data_dir)
    by_connector = storage.resolve_specialist_by_connector(plugin_data_dir, specialist_id)
    if len(by_connector) == 1:
        return by_connector[0]
    if len(by_connector) > 1:
        candidate_ids = _available_specialist_ids(by_connector)
        raise ModelRetry(
            t(
                locale,
                "errors.specialist_connector_ambiguous",
                id=specialist_id,
                candidates=candidate_ids,
            )
        )

    available = _available_specialist_ids(managed)
    raise ModelRetry(
        t(
            locale,
            "errors.specialist_not_found_with_available",
            id=specialist_id,
            available=available or t(locale, "errors.specialist_none_available"),
        )
    )


async def _delegate_specialist(
    ctx: RunContext[Any],
    *,
    specialist: JsonDict,
    task: str,
    context: str,
    mode: SpecialistDelegationMode,
) -> dict[str, Any]:
    locale = ctx.deps.context.locale
    plugin_data_dir = _plugin_data_dir(ctx)
    cloud_dir = specialist_run.resolve_cloud_plugin_data_dir(plugin_data_dir)
    tool_deps: ToolDeps | None = None
    if isinstance(ctx.deps, ToolDeps):
        tool_deps = ctx.deps

    rag_store = getattr(ctx.deps.project_client, "_rag_store", None)
    memory_text = ""
    if rag_store is not None and task.strip():
        memory_text, _ = await orchestrator._memory_context(  # noqa: SLF001
            rag_store,
            f"{task}\n{context}",
            locale=locale,
        )

    plugins_root = plugin_data_dir.parent
    parent_tool_call_id = getattr(ctx, "tool_call_id", None)
    try:
        if mode == "operative":
            content, degraded_tools = await specialist_run.run_operative(
                specialist=specialist,
                task=task,
                context=context,
                settings=get_settings(),
                provider_set=ctx.deps.context.provider_set,
                locale=locale,
                cloud_plugin_data_dir=cloud_dir,
                memory_text=memory_text,
                tool_deps=tool_deps,
                ui_mode=getattr(ctx.deps.context, "ui_mode", "agent"),
                plugins_root=plugins_root,
                parent_tool_call_id=parent_tool_call_id,
            )
        else:
            content, degraded_tools = await specialist_run.run_regard(
                specialist=specialist,
                question=task,
                context=context,
                settings=get_settings(),
                provider_set=ctx.deps.context.provider_set,
                locale=locale,
                cloud_plugin_data_dir=cloud_dir,
                memory_text=memory_text,
                tool_deps=tool_deps,
                ui_mode=getattr(ctx.deps.context, "ui_mode", "agent"),
                plugins_root=plugins_root,
                parent_tool_call_id=parent_tool_call_id,
            )
    except ValueError as exc:
        code = str(exc)
        detail = t(locale, f"errors.{code}")
        if detail == f"errors.{code}":
            detail = code
        raise ModelRetry(detail) from exc
    except Exception as exc:  # noqa: BLE001
        raise ModelRetry(f"{type(exc).__name__}: {exc}") from exc

    name = str(specialist.get("name") or specialist.get("id") or "")
    return {
        "specialist_id": specialist.get("id"),
        "specialist_name": name,
        "mode": mode,
        "content": content,
        "degraded_tools": degraded_tools,
        "display": "specialist_handoff_card",
        "human_summary": build_human_summary(
            "summon_specialist",
            {"name": name, "mode": mode, "task": task},
            result={"content": content},
            locale=locale,
        ),
    }


def register_personas_tools(agent: Agent[Any, str]) -> None:
    @agent.system_prompt
    async def business_agents_delegation_prompt(ctx: RunContext[Any]) -> str:
        locale = ctx.deps.context.locale
        try:
            plugin_data_dir = _plugin_data_dir(ctx)
        except ModelRetry:
            return ""
        specialists = storage.list_managed_specialists(plugin_data_dir)
        return build_business_agents_delegation_prompt(locale, specialists)

    @agent.tool
    async def summon_specialist(
        ctx: RunContext[Any],
        specialist_id: str,
        task: str,
        mode: str = "regard",
        context: str = "",
    ) -> dict[str, Any]:
        """Delegate to a managed business agent.

        Use the catalog id from the injected business-agents list; never a connector id
        unless it uniquely aliases one catalog agent.

        mode: regard = read-only tools; operative = full panel including writes (approval gate).
        Use for connector-backed tasks (Ihora timesheets, absences, ...). Prefer this over
        ask_personas when tools are needed.

        Args:
            specialist_id: Managed business agent identifier from the synced catalog.
            task: Task or question for the specialist.
            mode: ``regard`` (read-only tools) or ``operative`` (panel tools, writes via approval).
            context: Relevant excerpt from the current conversation.
        """
        locale = ctx.deps.context.locale
        plugin_data_dir = _plugin_data_dir(ctx)
        delegation_mode = _normalize_specialist_mode(mode, locale=locale)
        managed = storage.list_managed_specialists(plugin_data_dir)
        if not managed:
            return _summon_specialist_failure_result(
                specialist_id=specialist_id,
                mode=delegation_mode,
                locale=locale,
                error_code="no_business_agents_synced",
                content=t(locale, "errors.no_business_agents_synced"),
                task=task,
            )
        specialist = _resolve_specialist_for_summon(
            plugin_data_dir,
            specialist_id,
            locale=locale,
        )
        return await _delegate_specialist(
            ctx,
            specialist=specialist,
            task=task,
            context=context,
            mode=delegation_mode,
        )

    @agent.tool
    async def ask_personas(
        ctx: RunContext[Any],
        persona_ids: list[str],
        question: str,
        context: str = "",
    ) -> dict[str, Any]:
        """Ask one or more personas for their opinion on a topic.

        Returns structured opinions for inline display in the chat.

        Args:
            persona_ids: Persona identifiers (e.g. "01" for RH).
            question: Subject or question for the personas.
            context: Relevant excerpt from the current conversation, attached
                documents, or draft. Always pass a concise summary of what the
                user and assistant already discussed when the opinion relates
                to the ongoing chat.
        """
        locale = ctx.deps.context.locale
        plugin_data_dir = _plugin_data_dir(ctx)
        clamped_ids, _ = orchestrator.clamp_persona_ids(persona_ids, locale=locale)
        personas = storage.resolve_personas(plugin_data_dir, clamped_ids)
        if not personas:
            raise ModelRetry(t(locale, "errors.personas_not_found", ids=", ".join(persona_ids)))

        cloud_dir = specialist_run.resolve_cloud_plugin_data_dir(plugin_data_dir)
        tool_deps: ToolDeps | None = None
        if isinstance(ctx.deps, ToolDeps):
            tool_deps = ctx.deps

        rag_store = getattr(ctx.deps.project_client, "_rag_store", None)
        try:
            opinions, warnings, degraded_tools = await orchestrator.generate_opinions(
                plugin_data_dir=plugin_data_dir,
                persona_ids=clamped_ids,
                question=question,
                context=context,
                settings=get_settings(),
                provider_set=ctx.deps.context.provider_set,
                locale=locale,
                rag_store=rag_store,
                cloud_plugin_data_dir=cloud_dir,
                tool_deps=tool_deps,
                ui_mode=getattr(ctx.deps.context, "ui_mode", "agent"),
            )
        except ValueError as exc:
            code = str(exc)
            detail = t(locale, f"errors.{code}")
            if detail == f"errors.{code}":
                detail = code
            raise ModelRetry(detail) from exc
        except Exception as exc:  # noqa: BLE001
            raise ModelRetry(f"{type(exc).__name__}: {exc}") from exc

        return {
            "opinions": opinions,
            "warnings": warnings,
            "degraded_tools": degraded_tools,
            "display": "persona_opinion_card",
            "human_summary": build_human_summary(
                "ask_personas",
                {"names": _persona_label(personas), "question": question},
                result={"opinions": opinions},
                locale=locale,
            ),
        }

    @agent.tool
    async def simulate_meeting(
        ctx: RunContext[Any],
        persona_ids: list[str],
        topic: str,
        rounds: int = manifest.DEFAULT_ROUNDS,
    ) -> dict[str, Any]:
        """Start a simulated meeting between personas (dedicated full-screen view).

        The front opens the meeting view via the returned event metadata.

        Args:
            persona_ids: Participating persona identifiers.
            topic: Meeting subject.
            rounds: Number of discussion rounds (capped at 5).
        """
        locale = ctx.deps.context.locale
        plugin_data_dir = _plugin_data_dir(ctx)
        clamped_ids, persona_warnings = orchestrator.clamp_persona_ids(
            persona_ids, locale=locale
        )
        clamped_rounds, round_warnings = orchestrator.clamp_rounds(rounds, locale=locale)
        personas = storage.resolve_personas(plugin_data_dir, clamped_ids)
        if not personas:
            raise ModelRetry(t(locale, "errors.personas_not_found", ids=", ".join(persona_ids)))

        meeting_id = storage.new_meeting_id()
        names = _persona_label(personas)
        warnings = persona_warnings + round_warnings
        return {
            "action": "open_meeting_view",
            "meeting_id": meeting_id,
            "persona_ids": clamped_ids,
            "topic": topic,
            "rounds": clamped_rounds,
            "warnings": warnings,
            "human_summary": build_human_summary(
                "simulate_meeting",
                {"names": names, "topic": topic, "rounds": clamped_rounds},
                locale=locale,
            ),
        }
