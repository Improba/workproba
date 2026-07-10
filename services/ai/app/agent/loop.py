"""Boucle agent Workproba s'appuyant sur Pydantic AI.

`AgentLoop.run_turn` pilote `agent.iter(...)` (streaming bas-niveau du graphe)
et mappe les events Pydantic AI vers les SSE Workproba :
  - TextPart / TextPartDelta -> TokenEvent
  - FunctionToolCallEvent   -> ToolCallStartEvent
  - FunctionToolResultEvent -> ToolCallResultEvent
  - End node                -> DoneEvent

LiteLLM reste utilisé côté embeddings RAG (voir app.rag.store).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
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
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.usage import UsageLimits

from app.agent.confirmation import ConfirmationGate, confirmation_registry
from app.agent.human import build_human_summary
from app.agent.tools import ToolContext, ToolDeps
from app.limits import DEFAULT_LIMITS, Limits
from app.llm.provider import parse_tool_arguments
from app.project_client import ProjectClient
from app.sandbox.runner import SandboxRunner
from app.schemas import (
    AgentEvent,
    AgentTurnRequest,
    ChatMessage,
    DoneEvent,
    ErrorEvent,
    TokenEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
)
from pydantic_ai.messages import ModelMessage as _ModelMessage  # noqa: E402

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

    async def run_turn(self, request: AgentTurnRequest) -> AsyncIterator[AgentEvent]:
        gate = ConfirmationGate(session_id=request.session_id)
        await confirmation_registry.register(gate)
        output_queue: asyncio.Queue[AgentEvent | object] = asyncio.Queue()

        async def producer() -> None:
            try:
                async for event in self._run_turn_internal(request, gate):
                    await output_queue.put(event)
            finally:
                await output_queue.put(_SENTINEL)

        async def confirmation_drainer() -> None:
            while True:
                event = await gate.event_queue.get()
                await output_queue.put(event)

        producer_task = asyncio.create_task(producer())
        drainer_task = asyncio.create_task(confirmation_drainer())

        try:
            while True:
                event = await output_queue.get()
                if event is _SENTINEL:
                    break
                yield event  # type: ignore[misc]
        finally:
            gate.cancel_all()
            await confirmation_registry.unregister(request.session_id)
            producer_task.cancel()
            drainer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await producer_task
            with contextlib.suppress(asyncio.CancelledError):
                await drainer_task

    async def _run_turn_internal(
        self,
        request: AgentTurnRequest,
        gate: ConfirmationGate,
    ) -> AsyncIterator[AgentEvent]:
        context = ToolContext(
            tenant_id=request.tenant_id,
            project_id=request.project_id,
            session_id=request.session_id,
            documents=request.documents,
            project_root=self._project_root,
        )
        deps = ToolDeps(
            context=context,
            project_client=self._project_client,
            sandbox_runner=self._sandbox_runner,
            limits=self._limits,
            confirmation_gate=gate,
        )
        history = to_model_messages(request.history)

        try:
            async with self._agent.iter(
                user_prompt=request.message,
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
                        async for event in self._iter_tool_stream(node, run.ctx):
                            yield event
                    elif Agent.is_end_node(node):
                        output = run.result.output if run.result else ""
                        yield DoneEvent(
                            content=output if isinstance(output, str) else str(output),
                        )
        except UsageLimitExceeded:
            yield ErrorEvent(
                code="max_iterations_reached",
                message="Maximum agent iterations reached before final answer.",
            )
        except UnexpectedModelBehavior as exc:
            yield ErrorEvent(
                code="agent_model_error",
                message=f"Comportement modèle inattendu : {exc}",
            )

    async def _iter_model_stream(self, node: Any, ctx: Any) -> AsyncIterator[AgentEvent]:
        """Émet les deltas de texte du modèle comme TokenEvent.

        `AgentStream.stream_response()` yield des snapshots accumulés (ModelResponse
        entiers), ce qui dupliquerait le texte si on l'émettait brut. On utilise
        `stream_text(delta=True)` qui fournit les deltas incrémentaux. Les tool calls
        sont émis séparément via `_iter_tool_stream` (nœud CallToolsNode).
        """
        async with node.stream(ctx) as stream:
            async for delta in stream.stream_text(delta=True, debounce_by=None):
                if delta:
                    yield TokenEvent(content=delta)

    async def _iter_tool_stream(self, node: Any, ctx: Any) -> AsyncIterator[AgentEvent]:
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
                        ),
                    )
                elif isinstance(event, FunctionToolResultEvent):
                    part = event.part
                    tool_call_id = getattr(part, "tool_call_id", "") or ""
                    tool_name = getattr(part, "tool_name", "") or ""
                    arguments = pending_arguments.pop(tool_call_id, {})
                    result = coerce_tool_result(getattr(part, "content", None))
                    is_error = isinstance(part, RetryPromptPart)
                    if tool_name == "generate_document" and result.get("cancelled"):
                        is_error = True
                        human_summary = "Action annulée"
                    else:
                        human_summary = build_human_summary(
                            tool_name,
                            arguments,
                            result=result,
                            is_error=is_error,
                        )
                    yield ToolCallResultEvent(
                        tool_call_id=tool_call_id,
                        tool_name=tool_name,
                        result=result,
                        is_error=is_error,
                        human_summary=human_summary,
                    )


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
