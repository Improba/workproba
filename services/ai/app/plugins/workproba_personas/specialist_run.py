"""SpecialistRun modes Regard (lecture) et Opératoire (panel complet + HAG)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic_ai import Agent, RunContext, Tool

from app.agent.tools import ToolContext, ToolDeps
from app.i18n import t
from app.limits import DEFAULT_LIMITS
from app.llm.config import build_model, build_model_settings, resolve_llm_config
from app.sandbox.runner import SandboxRunner
from app.schemas import DocumentContent, FileListResponse, KnowledgeSearchResponse, ProviderSet
from app.plugins.workproba_cloud.plugin import (
    invoke_managed_connector_impl,
    normalize_tool_input_schema,
    should_register_managed_tool,
)
from app.plugins.workproba_personas import prompts
from app.plugins.workproba_personas.storage import JsonDict
from app.plugins.workproba_personas.tool_allowlist import (
    DegradedTool,
    PanelToolsResolution,
    ResolvedPanelTool,
    ResolvedReadTool,
    ToolFilter,
    active_connectors_snapshot,
    resolve_panel_tools,
    resolve_tool_filter,
)

SpecialistRunModeLiteral = Literal["regard", "operative"]


class _RegardProjectClient:
    """Client projet minimal pour les runs Regard hors boucle agent principale."""

    async def close(self) -> None:
        return None

    async def list_files(
        self,
        *,
        subdir: str = "",
        max_entries: int = 0,
    ) -> FileListResponse:
        _ = (subdir, max_entries)
        return FileListResponse(root="", entries=[], truncated=False)

    async def search_kb(
        self,
        *,
        tenant_id: str,
        project_id: str,
        query: str,
        limit: int = 8,
        filters: dict[str, Any] | None = None,
    ) -> KnowledgeSearchResponse:
        _ = (tenant_id, project_id, query, limit, filters)
        return KnowledgeSearchResponse(results=[])

    async def read_document(
        self,
        *,
        tenant_id: str,
        project_id: str,
        document_id: str,
        offset_lines: int = 0,
        max_lines: int = 0,
    ) -> DocumentContent:
        _ = (tenant_id, project_id, document_id, offset_lines, max_lines)
        return DocumentContent(document_id=document_id, name=document_id, text="", mime_type="text/plain")

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
        _ = (tenant_id, project_id, session_id, name, mime_type, content_base64, metadata)
        return DocumentContent(document_id=name, name=name, text="", mime_type=mime_type)


def resolve_cloud_plugin_data_dir(plugin_data_dir: Path | str | None) -> Path | None:
    if plugin_data_dir is None:
        return None
    from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD

    base = Path(plugin_data_dir).expanduser().resolve().parent
    return base / PLUGIN_WORKPROBA_CLOUD


def build_regard_tool_deps(
    *,
    plugins_root: Path,
    locale: str,
    cloud_plugin_data_dir: Path | None = None,
    ui_mode: str = "agent",
    permissions_network: bool = True,
    managed_allowed_connector_ids: frozenset[str] | None = None,
    confirmation_gate: Any = None,
    project_client: Any = None,
) -> ToolDeps:
    allowed = managed_allowed_connector_ids
    if allowed is None and cloud_plugin_data_dir is not None:
        allowed = frozenset(
            str(connector.get("id"))
            for connector in active_connectors_snapshot(cloud_plugin_data_dir)
            if connector.get("id")
        )
    return ToolDeps(
        context=ToolContext(
            tenant_id="",
            project_id="",
            session_id="regard",
            documents=[],
            plugin_data_dir=plugins_root,
            locale=locale,
            permissions_network=permissions_network,
            managed_allowed_connector_ids=allowed,
            ui_mode=ui_mode,
        ),
        project_client=project_client or _RegardProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
        confirmation_gate=confirmation_gate,
    )


def specialist_has_panel_tools(persona: JsonDict) -> bool:
    if persona.get("is_business_agent") is not True:
        return False
    tools = persona.get("tools")
    if not isinstance(tools, dict):
        return False
    allowed = tools.get("allowed")
    return isinstance(allowed, list) and bool(allowed)


def build_specialist_system_prompt(
    specialist: JsonDict,
    *,
    locale: str,
    resolution: PanelToolsResolution | None = None,
    mode: SpecialistRunModeLiteral = "regard",
    tool_filter: ToolFilter | None = None,
) -> str:
    base = str(specialist.get("system_prompt") or "").strip()
    doctrine = specialist.get("doctrine")
    if isinstance(doctrine, dict):
        doctrine_parts: list[str] = []
        mission = doctrine.get("mission")
        if isinstance(mission, str) and mission.strip():
            doctrine_parts.append(mission.strip())
        principles = doctrine.get("principles")
        if isinstance(principles, list):
            doctrine_parts.extend(
                str(item).strip()
                for item in principles
                if isinstance(item, str) and item.strip()
            )
        if doctrine_parts:
            doctrine_text = "\n".join(doctrine_parts)
            base = f"{base}\n\n{doctrine_text}".strip() if base else doctrine_text
    base = prompts.build_persona_system_prompt(base, locale=locale)
    if resolution is not None:
        effective_filter = tool_filter or resolve_tool_filter(specialist, mode)
        if effective_filter == "disabled":
            available: list[str] = []
        elif mode == "operative" and effective_filter == "allowlist":
            available = [tool.managed_name for tool in resolution.allowed_panel_tools]
        else:
            available = [tool.managed_name for tool in resolution.allowed_read_tools]
        degraded = [entry.to_dict() for entry in resolution.degraded_tools]
        notice = prompts.build_panel_tools_notice(
            available_tools=available,
            degraded_tools=degraded,
            locale=locale,
        )
        if notice:
            base = f"{base}\n\n{notice}".strip()
    return base


def _effect_blocked_response(
    *,
    locale: str,
    reason: str,
    managed_name: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "error": reason,
        "tool": managed_name,
        "human_summary": t(locale, f"personas.specialist_run.{reason}", tool=managed_name),
    }


def _make_panel_tool_shim(
    connector_id: str,
    tool_def: JsonDict,
    *,
    managed_name: str,
    require_read: bool,
):
    action = str(tool_def["action"])
    effect = str(tool_def.get("effect") or "")

    async def _shim(ctx: RunContext[ToolDeps], **kwargs: Any) -> dict[str, Any]:
        locale = ctx.deps.context.locale
        if require_read and effect != "read":
            return _effect_blocked_response(
                locale=locale,
                reason="effect_not_read",
                managed_name=managed_name,
            )
        kwargs.pop("action", None)
        payload: dict[str, Any] = {}
        for key, value in kwargs.items():
            if value is not None:
                payload[key] = value
        payload["action"] = action
        return await invoke_managed_connector_impl(
            ctx,
            connector_id=connector_id,
            payload=payload,
            gate_tool_name=managed_name,
        )

    return _shim


def _make_read_tool_shim(
    connector_id: str,
    tool_def: JsonDict,
    *,
    managed_name: str,
):
    return _make_panel_tool_shim(
        connector_id,
        tool_def,
        managed_name=managed_name,
        require_read=True,
    )


def _register_panel_tools(
    agent: Agent[ToolDeps, str],
    tools: list[ResolvedPanelTool],
    *,
    ui_mode: str,
    require_read: bool,
) -> None:
    for resolved in tools:
        tool_def = resolved.tool_def
        effect = str(tool_def.get("effect") or "")
        if require_read and effect != "read":
            continue
        if not should_register_managed_tool(tool_def, ui_mode):  # type: ignore[arg-type]
            continue
        description = str(tool_def.get("description") or resolved.tool_name).strip()
        json_schema = normalize_tool_input_schema(tool_def.get("input_schema"))
        shim = _make_panel_tool_shim(
            resolved.connector_id,
            tool_def,
            managed_name=resolved.managed_name,
            require_read=require_read,
        )
        tool = Tool.from_schema(
            shim,
            name=resolved.managed_name,
            description=description,
            json_schema=json_schema,
            takes_ctx=True,
        )
        agent._function_toolset.add_tool(tool)


def register_regard_tools(
    agent: Agent[ToolDeps, str],
    allowed_read_tools: list[ResolvedReadTool],
    *,
    ui_mode: str,
) -> None:
    """Enregistre uniquement les tools read du panel ; pas de fallback générique."""
    panel_tools = [
        ResolvedPanelTool(
            connector_id=tool.connector_id,
            tool_name=tool.tool_name,
            managed_name=tool.managed_name,
            tool_def=tool.tool_def,
            effect="read",
        )
        for tool in allowed_read_tools
        if str(tool.tool_def.get("effect") or "") == "read"
    ]
    _register_panel_tools(agent, panel_tools, ui_mode=ui_mode, require_read=True)


def register_operative_tools(
    agent: Agent[ToolDeps, str],
    allowed_panel_tools: list[ResolvedPanelTool],
    *,
    ui_mode: str,
) -> None:
    """Enregistre les tools read+write du panel ; writes passent par HAG via invoke."""
    _register_panel_tools(
        agent,
        allowed_panel_tools,
        ui_mode=ui_mode,
        require_read=False,
    )


def build_specialist_agent(
    *,
    settings: Any,
    provider_set: ProviderSet | None,
    system_prompt: str,
    resolution: PanelToolsResolution,
    mode: SpecialistRunModeLiteral = "regard",
    tool_filter: ToolFilter | None = None,
    specialist: JsonDict | None = None,
    ui_mode: str = "agent",
    cloud_plugin_data_dir: Path | str | None = None,
) -> Agent[ToolDeps, str]:
    llm_config = resolve_llm_config(
        None,
        settings,
        provider_set=provider_set,
        cloud_plugin_data_dir=cloud_plugin_data_dir,
    )
    agent: Agent[ToolDeps, str] = Agent(
        build_model(llm_config),
        system_prompt=system_prompt,
        output_type=str,
        model_settings=build_model_settings(llm_config, provider_set),
        deps_type=ToolDeps,
    )
    effective_filter = tool_filter
    if effective_filter is None:
        effective_filter = resolve_tool_filter(specialist or {}, mode)
    if effective_filter != "disabled":
        if mode == "regard" or effective_filter == "pure_read":
            register_regard_tools(agent, resolution.allowed_read_tools, ui_mode=ui_mode)
        else:
            register_operative_tools(
                agent,
                resolution.allowed_panel_tools,
                ui_mode=ui_mode,
            )
    return agent


def build_regard_agent(
    *,
    settings: Any,
    provider_set: ProviderSet | None,
    system_prompt: str,
    allowed_read_tools: list[ResolvedReadTool],
    ui_mode: str = "agent",
    cloud_plugin_data_dir: Path | str | None = None,
) -> Agent[ToolDeps, str]:
    resolution = PanelToolsResolution(
        allowed_read_tools=allowed_read_tools,
        allowed_panel_tools=[
            ResolvedPanelTool(
                connector_id=tool.connector_id,
                tool_name=tool.tool_name,
                managed_name=tool.managed_name,
                tool_def=tool.tool_def,
                effect="read",
            )
            for tool in allowed_read_tools
        ],
    )
    return build_specialist_agent(
        settings=settings,
        provider_set=provider_set,
        system_prompt=system_prompt,
        resolution=resolution,
        mode="regard",
        ui_mode=ui_mode,
        cloud_plugin_data_dir=cloud_plugin_data_dir,
    )


def resolve_specialist_panel(
    specialist: JsonDict,
    cloud_plugin_data_dir: Path | None,
    *,
    mode: SpecialistRunModeLiteral = "regard",
) -> PanelToolsResolution:
    if cloud_plugin_data_dir is None:
        refs = []
        tools = specialist.get("tools")
        if isinstance(tools, dict):
            allowed_raw = tools.get("allowed")
            refs = [entry for entry in (allowed_raw or []) if isinstance(entry, dict)]
        degraded = [
            DegradedTool(
                str(entry.get("connector_id") or ""),
                str(entry.get("tool") or ""),
                "connector_unavailable",
            )
            for entry in refs
            if entry.get("connector_id") and entry.get("tool")
        ]
        return PanelToolsResolution(degraded_tools=degraded)
    snapshot = active_connectors_snapshot(cloud_plugin_data_dir)
    return resolve_panel_tools(specialist, snapshot, mode=mode)


def resolve_regard_panel(
    specialist: JsonDict,
    cloud_plugin_data_dir: Path | None,
) -> PanelToolsResolution:
    return resolve_specialist_panel(specialist, cloud_plugin_data_dir, mode="regard")


async def run_specialist(
    *,
    specialist: JsonDict,
    task: str,
    context: str,
    settings: Any,
    provider_set: ProviderSet | None,
    locale: str,
    mode: SpecialistRunModeLiteral = "regard",
    cloud_plugin_data_dir: Path | None = None,
    memory_text: str = "",
    tool_deps: ToolDeps | None = None,
    ui_mode: str = "agent",
    plugins_root: Path | None = None,
    parent_tool_call_id: str | None = None,
) -> tuple[str, list[JsonDict]]:
    """Exécute un tour SpecialistRun. Retourne (contenu, degraded_tools)."""
    from app.agent.loop import iter_nested_tool_stream, map_model_stream_events

    effective_cloud_dir = cloud_plugin_data_dir
    if effective_cloud_dir is None and plugins_root is not None:
        effective_cloud_dir = resolve_cloud_plugin_data_dir(plugins_root / "workproba.personas")

    resolution = resolve_specialist_panel(specialist, effective_cloud_dir, mode=mode)
    degraded = [entry.to_dict() for entry in resolution.degraded_tools]

    effective_deps = tool_deps
    if effective_deps is None:
        root = plugins_root
        if root is None and effective_cloud_dir is not None:
            root = effective_cloud_dir.parent
        if root is None:
            raise ValueError("regard_tool_deps_missing")
        effective_deps = build_regard_tool_deps(
            plugins_root=root,
            locale=locale,
            cloud_plugin_data_dir=effective_cloud_dir,
            ui_mode=ui_mode,
        )

    if mode == "operative" and effective_deps.confirmation_gate is None:
        raise ValueError("operative_confirmation_gate_required")

    event_queue = effective_deps.event_queue
    tool_filter = resolve_tool_filter(specialist, mode)

    system_prompt = build_specialist_system_prompt(
        specialist,
        locale=locale,
        resolution=resolution,
        mode=mode,
        tool_filter=tool_filter,
    )
    user_prompt = prompts.build_opinion_user_prompt(
        question=task,
        context=context,
        memory_text=memory_text,
        locale=locale,
    )
    agent = build_specialist_agent(
        settings=settings,
        provider_set=provider_set,
        system_prompt=system_prompt,
        resolution=resolution,
        mode=mode,
        tool_filter=tool_filter,
        specialist=specialist,
        ui_mode=ui_mode,
        cloud_plugin_data_dir=effective_cloud_dir,
    )

    output = ""
    async with agent.iter(user_prompt, deps=effective_deps) as run:
        model_round = 0
        async for node in run:
            if Agent.is_model_request_node(node):
                async with node.stream(run.ctx) as stream:
                    async for event in map_model_stream_events(
                        stream,
                        model_round=model_round,
                        parent_tool_call_id=parent_tool_call_id,
                    ):
                        if event_queue is not None:
                            await event_queue.put(event)
                model_round += 1
            elif Agent.is_call_tools_node(node):
                async for event in iter_nested_tool_stream(
                    node,
                    run.ctx,
                    locale=locale,
                    parent_tool_call_id=parent_tool_call_id,
                ):
                    if event_queue is not None:
                        await event_queue.put(event)
            elif Agent.is_end_node(node):
                raw_output = run.result.output if run.result else ""
                output = raw_output.strip() if isinstance(raw_output, str) else str(raw_output).strip()

    return output, degraded


async def run_regard(
    *,
    specialist: JsonDict,
    question: str,
    context: str,
    settings: Any,
    provider_set: ProviderSet | None,
    locale: str,
    cloud_plugin_data_dir: Path | None = None,
    memory_text: str = "",
    tool_deps: ToolDeps | None = None,
    ui_mode: str = "agent",
    plugins_root: Path | None = None,
    parent_tool_call_id: str | None = None,
) -> tuple[str, list[JsonDict]]:
    """Exécute un tour Regard pour un agent métier. Retourne (contenu, degraded_tools)."""
    return await run_specialist(
        specialist=specialist,
        task=question,
        context=context,
        settings=settings,
        provider_set=provider_set,
        locale=locale,
        mode="regard",
        cloud_plugin_data_dir=cloud_plugin_data_dir,
        memory_text=memory_text,
        tool_deps=tool_deps,
        ui_mode=ui_mode,
        plugins_root=plugins_root,
        parent_tool_call_id=parent_tool_call_id,
    )


async def run_operative(
    *,
    specialist: JsonDict,
    task: str,
    context: str,
    settings: Any,
    provider_set: ProviderSet | None,
    locale: str,
    cloud_plugin_data_dir: Path | None = None,
    memory_text: str = "",
    tool_deps: ToolDeps | None = None,
    ui_mode: str = "agent",
    plugins_root: Path | None = None,
    parent_tool_call_id: str | None = None,
) -> tuple[str, list[JsonDict]]:
    """Exécute un tour opératoire (panel read+write, HAG obligatoire sur write)."""
    return await run_specialist(
        specialist=specialist,
        task=task,
        context=context,
        settings=settings,
        provider_set=provider_set,
        locale=locale,
        mode="operative",
        cloud_plugin_data_dir=cloud_plugin_data_dir,
        memory_text=memory_text,
        tool_deps=tool_deps,
        ui_mode=ui_mode,
        plugins_root=plugins_root,
        parent_tool_call_id=parent_tool_call_id,
    )
