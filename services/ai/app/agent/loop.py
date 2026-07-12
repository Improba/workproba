"""Boucle agent Workproba s'appuyant sur Pydantic AI.

`AgentLoop.run_turn` pilote `agent.iter(...)` (streaming bas-niveau du graphe)
et mappe les events Pydantic AI vers les SSE Workproba :
  - TextPart / TextPartDelta -> TokenEvent
  - ThinkingPart / ThinkingPartDelta -> ThinkingStartEvent / ThinkingDeltaEvent / ThinkingEndEvent
  - FunctionToolCallEvent   -> ToolCallStartEvent
  - FunctionToolResultEvent -> ToolCallResultEvent
  - End node                -> DoneEvent

LiteLLM reste utilisé côté embeddings RAG (voir app.rag.store).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.usage import UsageLimits

from app.agent.attachments import build_user_prompt, process_inline_attachments
from app.agent.confirmation import ConfirmationGate, confirmation_registry
from app.agent.human import build_human_summary
from app.agent.plan import PlanGate, plan_registry
from app.agent.tools import ToolContext, ToolDeps
from app.i18n import t
from app.limits import DEFAULT_LIMITS, Limits
from app.llm.provider import parse_tool_arguments
from app.llm.utility import extract_usage_tokens
from app.plugins.hooks import hook_registry
from app.plugins.registry import build_plugin_contexts, register_plugin_hooks
from app.project_client import ProjectClient
from app.provider_set import resolve_provider_set
from app.sandbox.runner import SandboxRunner
from app.schemas import (
    AgentEvent,
    AgentTurnRequest,
    AttachmentStatusEvent,
    ChatMessage,
    DoneEvent,
    ErrorEvent,
    ThinkingDeltaEvent,
    ThinkingEndEvent,
    ThinkingStartEvent,
    TokenEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
)
from pydantic_ai.messages import ModelMessage as _ModelMessage  # noqa: E402

logger = logging.getLogger(__name__)

_SENTINEL = object()


class AgentLoop:
    def __init__(
        self,
        *,
        agent: Agent[ToolDeps, str],
        project_client: ProjectClient,
        sandbox_runner: SandboxRunner,
        max_iterations: int,
        model_settings: dict[str, Any] | None = None,
        project_root: Path | None = None,
        limits: Limits = DEFAULT_LIMITS,
    ) -> None:
        self._agent = agent
        self._project_client = project_client
        self._sandbox_runner = sandbox_runner
        self._max_iterations = max_iterations
        self._model_settings = model_settings or {}
        self._project_root = project_root
        self._limits = limits

    async def run_turn(
        self,
        request: AgentTurnRequest,
        *,
        turn_id: str,
        cancel_event: asyncio.Event | None = None,
    ) -> AsyncIterator[AgentEvent]:
        gate = ConfirmationGate(session_id=request.session_id, turn_id=turn_id)
        plan_gate = PlanGate(session_id=request.session_id, turn_id=turn_id)
        await confirmation_registry.register(gate)
        await plan_registry.register(plan_gate)
        output_queue: asyncio.Queue[AgentEvent | object] = asyncio.Queue()
        cancel = cancel_event or asyncio.Event()

        async def producer() -> None:
            try:
                async for event in self._run_turn_internal(request, gate, plan_gate):
                    if cancel.is_set():
                        break
                    await output_queue.put(event)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "Unhandled agent turn error (session=%s turn=%s)",
                    request.session_id,
                    turn_id,
                )
                await output_queue.put(
                    ErrorEvent(
                        code="internal_error",
                        message=t(request.locale, "loop.internal_error"),
                    )
                )
            finally:
                await output_queue.put(_SENTINEL)

        async def confirmation_drainer() -> None:
            while not cancel.is_set():
                try:
                    event = await asyncio.wait_for(gate.event_queue.get(), timeout=0.5)
                except TimeoutError:
                    continue
                if cancel.is_set():
                    break
                await output_queue.put(event)

        async def plan_drainer() -> None:
            while not cancel.is_set():
                try:
                    event = await asyncio.wait_for(plan_gate.event_queue.get(), timeout=0.5)
                except TimeoutError:
                    continue
                if cancel.is_set():
                    break
                await output_queue.put(event)

        producer_task = asyncio.create_task(producer())
        drainer_task = asyncio.create_task(confirmation_drainer())
        plan_drainer_task = asyncio.create_task(plan_drainer())

        try:
            while True:
                if cancel.is_set():
                    break
                try:
                    event = await asyncio.wait_for(output_queue.get(), timeout=0.5)
                except TimeoutError:
                    continue
                if event is _SENTINEL:
                    break
                yield event  # type: ignore[misc]
        finally:
            cancel.set()
            gate.cancel_all()
            plan_gate.cancel_all()
            await confirmation_registry.unregister(request.session_id, turn_id)
            await plan_registry.unregister(request.session_id, turn_id)
            producer_task.cancel()
            drainer_task.cancel()
            plan_drainer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await producer_task
            with contextlib.suppress(asyncio.CancelledError):
                await drainer_task
            with contextlib.suppress(asyncio.CancelledError):
                await plan_drainer_task

    async def _run_turn_internal(
        self,
        request: AgentTurnRequest,
        gate: ConfirmationGate,
        plan_gate: PlanGate,
    ) -> AsyncIterator[AgentEvent]:
        workspace_data_dir = (
            Path(request.workspace_data_dir).expanduser().resolve()
            if request.workspace_data_dir
            else None
        )
        # Sépare les pièces jointes inline (content_base64) des documents projet
        # (présents sur disque, accessibles via read_document). Les premières sont
        # textualisées et injectées dans le prompt utilisateur ; les secondes
        # restent listées dans l'inventaire projet pour l'outil.
        inline_docs = [d for d in request.documents if d.content_base64]
        project_docs = [d for d in request.documents if not d.content_base64]
        provider_set = resolve_provider_set(request.provider_set)
        processed = await process_inline_attachments(
            inline_docs,
            self._limits,
            locale=request.locale,
            provider_set=provider_set,
            ui_mode=request.ui_mode,
        )
        for status in processed.statuses:
            yield AttachmentStatusEvent(
                message_id=request.session_id,
                attachment_id=status.attachment_id,
                status_key=status.status_key,
                label_locale=status.label_locale,
            )
        user_prompt = build_user_prompt(request.message, processed)
        plugin_data_dir = (
            Path(request.plugin_data_dir).expanduser().resolve()
            if request.plugin_data_dir
            else None
        )
        register_plugin_hooks(request.active_plugins)
        plugin_contexts = build_plugin_contexts(
            active_plugins=request.active_plugins,
            plugin_data_dir=plugin_data_dir,
            locale=request.locale,
            provider_set=provider_set,
            workspace_data_dir=workspace_data_dir,
            project_root=self._project_root,
        )
        context = ToolContext(
            tenant_id=request.tenant_id or "",
            project_id=request.project_id,
            session_id=request.session_id,
            documents=project_docs,
            project_root=self._project_root,
            workspace_data_dir=workspace_data_dir,
            workspace_title=request.workspace_title,
            locale=request.locale,
            active_plugins=request.active_plugins,
            plugin_data_dir=plugin_data_dir,
            provider_set=provider_set,
            settings_locked=request.settings_locked,
            permissions_network=request.permissions_network,
            code_execute=request.code_execute,
            audit_retention_days=request.audit_retention_days,
            audit_enabled=request.audit_enabled,
        )
        deps = ToolDeps(
            context=context,
            project_client=self._project_client,
            sandbox_runner=self._sandbox_runner,
            limits=self._limits,
            confirmation_gate=gate,
            plan_gate=plan_gate,
        )
        history = to_model_messages(request.history)
        turn_summary = ""
        hook_payload_base = {
            "turn_id": gate.turn_id,
            "_plugin_contexts": plugin_contexts,
        }
        hook_registry.dispatch(
            "turn.started",
            {**hook_payload_base},
        )

        try:
            async with self._agent.iter(
                user_prompt=user_prompt,
                message_history=history,
                deps=deps,
                model_settings=self._model_settings or None,
                usage_limits=UsageLimits(request_limit=self._max_iterations),
            ) as run:
                async for node in run:
                    if Agent.is_model_request_node(node):
                        async for event in self._iter_model_stream(node, run.ctx):
                            yield event
                    elif Agent.is_call_tools_node(node):
                        async for event in self._iter_tool_stream(
                            node,
                            run.ctx,
                            locale=request.locale,
                            hook_payload_base=hook_payload_base,
                        ):
                            yield event
                    elif Agent.is_end_node(node):
                        output = run.result.output if run.result else ""
                        turn_summary = output if isinstance(output, str) else str(output)
                        input_tokens, output_tokens, total_tokens = extract_usage_tokens(
                            run.result or run
                        )
                        hook_registry.dispatch(
                            "turn.completed",
                            {
                                **hook_payload_base,
                                "summary": turn_summary,
                            },
                        )
                        yield DoneEvent(
                            content=output if isinstance(output, str) else str(output),
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            total_tokens=total_tokens,
                        )
        except UsageLimitExceeded:
            yield ErrorEvent(
                code="usage_limit_exceeded",
                message=t(request.locale, "loop.usage_limit_exceeded"),
            )
        except UnexpectedModelBehavior as exc:
            yield ErrorEvent(
                code="unexpected_model_behavior",
                message=t(
                    request.locale,
                    "loop.unexpected_model_behavior",
                    detail=exc,
                ),
            )
        except Exception:
            logger.exception(
                "Agent iteration failed (session=%s)",
                request.session_id,
            )
            yield ErrorEvent(
                code="internal_error",
                message=t(request.locale, "loop.internal_error"),
            )

    async def _iter_model_stream(self, node: Any, ctx: Any) -> AsyncIterator[AgentEvent]:
        """Émet les deltas de texte et de raisonnement du modèle."""
        async with node.stream(ctx) as stream:
            async for event in map_model_stream_events(stream):
                yield event

    async def _iter_tool_stream(
        self,
        node: Any,
        ctx: Any,
        *,
        locale: str,
        hook_payload_base: dict[str, Any] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        from pydantic_ai.messages import FunctionToolCallEvent, FunctionToolResultEvent

        pending_arguments: dict[str, dict[str, Any]] = {}
        async with node.stream(ctx) as tool_stream:
            async for event in tool_stream:
                if isinstance(event, FunctionToolCallEvent):
                    part = event.part
                    arguments = parse_tool_arguments(part.args)
                    pending_arguments[part.tool_call_id] = arguments
                    yield ToolCallStartEvent(
                        tool_call_id=part.tool_call_id,
                        tool_name=part.tool_name,
                        arguments=arguments,
                        human_summary=build_human_summary(
                            part.tool_name,
                            arguments,
                            locale=locale,
                        ),
                    )
                elif isinstance(event, FunctionToolResultEvent):
                    part = event.part
                    tool_call_id = getattr(part, "tool_call_id", "") or ""
                    tool_name = getattr(part, "tool_name", "") or ""
                    arguments = pending_arguments.pop(tool_call_id, {})
                    result = coerce_tool_result(getattr(part, "content", None))
                    is_error = isinstance(part, RetryPromptPart)
                    if tool_name in {
                        "generate_document",
                        "write_docx",
                        "write_xlsx",
                        "write_pdf",
                        "publish_artifact",
                    } and result.get("cancelled"):
                        is_error = True
                        human_summary = t(locale, "loop.action_cancelled")
                    elif tool_name == "propose_plan" and result.get("cancelled"):
                        is_error = True
                        human_summary = t(locale, "plan.denied")
                    else:
                        human_summary = build_human_summary(
                            tool_name,
                            arguments,
                            result=result,
                            is_error=is_error,
                            locale=locale,
                        )
                    yield ToolCallResultEvent(
                        tool_call_id=tool_call_id,
                        tool_name=tool_name,
                        result=result,
                        is_error=is_error,
                        human_summary=human_summary,
                    )
                    if hook_payload_base is not None:
                        hook_registry.dispatch(
                            "tool.call_completed",
                            {
                                **hook_payload_base,
                                "tool": tool_name,
                                "args": arguments,
                                "result": result,
                                "is_error": is_error,
                            },
                        )


async def map_model_stream_events(stream: Any) -> AsyncIterator[AgentEvent]:
    """Mappe les ModelResponseStreamEvent Pydantic AI vers les events SSE Workproba."""
    from pydantic_ai.messages import (
        PartDeltaEvent,
        PartEndEvent,
        PartStartEvent,
        TextPart,
        TextPartDelta,
        ThinkingPart,
        ThinkingPartDelta,
    )

    async for event in stream:
        if isinstance(event, PartStartEvent):
            if isinstance(event.part, ThinkingPart):
                yield ThinkingStartEvent(thinking_id=_thinking_id(event.index))
                # pydantic-ai embarque le premier chunk de raisonnement dans le
                # PartStartEvent (pas de PartDeltaEvent séparé) : il faut le
                # relayer comme ThinkingDeltaEvent, sinon le début du thinking
                # est perdu du flux SSE.
                start_text = event.part.content or ""
                if start_text:
                    yield ThinkingDeltaEvent(
                        thinking_id=_thinking_id(event.index),
                        content=start_text,
                    )
            elif isinstance(event.part, TextPart):
                # Idem pour la réponse : le premier token texte vit dans le
                # PartStartEvent. Sans ce relais, le début de la réponse
                # disparaît du stream (ex. "4" manquant à "2+2 = ?"). Le
                # fallback `done` côté front ne rattrape que les réponses
                # tenant en un seul chunk.
                start_text = event.part.content or ""
                if start_text:
                    yield TokenEvent(content=start_text)
            continue
        if isinstance(event, PartDeltaEvent):
            if isinstance(event.delta, ThinkingPartDelta):
                delta_text = event.delta.content_delta or ""
                if delta_text:
                    yield ThinkingDeltaEvent(
                        thinking_id=_thinking_id(event.index),
                        content=delta_text,
                    )
            elif isinstance(event.delta, TextPartDelta):
                delta_text = event.delta.content_delta or ""
                if delta_text:
                    yield TokenEvent(content=delta_text)
        elif isinstance(event, PartEndEvent):
            if isinstance(event.part, ThinkingPart):
                yield ThinkingEndEvent(thinking_id=_thinking_id(event.index))


def _thinking_id(index: int) -> str:
    return f"think-{index}"


def to_model_messages(history: list[ChatMessage]) -> list[_ModelMessage]:
    """Convertit l'historique Workproba en messages Pydantic AI."""
    messages: list[_ModelMessage] = []
    for message in history:
        if message.role == "system":
            messages.append(
                ModelRequest([SystemPromptPart(content=message.content or "")])
            )
        elif message.role == "user":
            messages.append(
                ModelRequest([UserPromptPart(content=message.content or "")])
            )
        elif message.role == "assistant":
            parts: list[Any] = []
            if message.thinking:
                parts.append(ThinkingPart(content=message.thinking))
            if message.content:
                parts.append(TextPart(content=message.content))
            for tool_call in message.tool_calls:
                parts.append(
                    ToolCallPart(
                        tool_name=tool_call.name,
                        args=tool_call.arguments,
                        tool_call_id=tool_call.id,
                    )
                )
            messages.append(ModelResponse(parts=parts))
        elif message.role == "tool":
            messages.append(
                ModelRequest(
                    [
                        ToolReturnPart(
                            tool_name=message.name or "",
                            content=message.content or "",
                            tool_call_id=message.tool_call_id or "",
                        )
                    ]
                )
            )
    return messages


def coerce_tool_result(content: Any) -> dict[str, Any]:
    if isinstance(content, dict):
        return content
    if content is None:
        return {}
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return {"content": content}
        return parsed if isinstance(parsed, dict) else {"content": content}
    return {"content": str(content)}
