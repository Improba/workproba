"""Tests unitaires + intégration : boucle agent Pydantic AI.

On pilote l'agent avec `TestModel` (sans LLM réel) pour valider le mapping
des events Pydantic AI -> SSE Workproba et la robustesse des outils
(échecs -> ModelRetry -> ToolCallResultEvent is_error).
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.messages import (
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
)

from app.agent.loop import (
    AgentLoop,
    coerce_tool_result,
    map_model_stream_events,
    to_model_messages,
)
from app.agent.tools import ToolContext, build_agent
from app.schemas import (
    AgentTurnRequest,
    ChatMessage,
    DoneEvent,
    ErrorEvent,
    ThinkingDeltaEvent,
    ThinkingEndEvent,
    ThinkingStartEvent,
    TokenEvent,
    ToolCall,
    ToolCallResultEvent,
    ToolCallStartEvent,
)
from app.sandbox.runner import SandboxRunner

from conftest import FakeProjectClient


def _make_request(message: str = "lire") -> AgentTurnRequest:
    return AgentTurnRequest(
        tenant_id="t",
        project_id="p",
        session_id="s",
        message=message,
        documents=[],
    )


def _event_types(events: list[Any]) -> list[str]:
    return [type(e).__name__ for e in events]


async def _run(loop: AgentLoop, request: AgentTurnRequest, *, turn_id: str = "turn-test") -> list[Any]:
    return [event async for event in loop.run_turn(request, turn_id=turn_id)]


def _new_loop(client: FakeProjectClient, *, max_iterations: int = 6) -> AgentLoop:
    agent = build_agent(TestModel(seed=0, call_tools=["read_document"]))
    return AgentLoop(
        agent=agent,
        project_client=client,
        sandbox_runner=SandboxRunner(timeout_seconds=10),
        max_iterations=max_iterations,
    )


# --- to_model_messages -----------------------------------------------------


def test_to_model_messages_user_assistant_tool() -> None:
    history = [
        ChatMessage(role="user", content="bonjour"),
        ChatMessage(
            role="assistant",
            content="je cherche",
            tool_calls=[ToolCall(id="tc1", name="search_kb", arguments={"query": "x"})],
        ),
        ChatMessage(role="tool", name="search_kb", tool_call_id="tc1", content='{"r": []}'),
        ChatMessage(role="assistant", content="voila"),
    ]
    msgs = to_model_messages(history)
    assert len(msgs) == 4
    kinds = [m.kind for m in msgs]
    assert kinds == ["request", "response", "request", "response"]


def test_to_model_messages_system() -> None:
    msgs = to_model_messages([ChatMessage(role="system", content="tu es WP")])
    assert len(msgs) == 1
    assert msgs[0].kind == "request"


def test_to_model_messages_assistant_only_tool_calls() -> None:
    msgs = to_model_messages(
        [
            ChatMessage(
                role="assistant",
                content=None,
                tool_calls=[ToolCall(id="tc1", name="read_document", arguments={"document_id": "a"})],
            )
        ]
    )
    assert len(msgs) == 1
    assert msgs[0].kind == "response"
    assert len(msgs[0].parts) == 1  # only the ToolCallPart (no empty TextPart)


def test_to_model_messages_assistant_with_thinking() -> None:
    msgs = to_model_messages(
        [
            ChatMessage(
                role="assistant",
                thinking="some reasoning",
                content="answer",
            )
        ]
    )
    assert len(msgs) == 1
    assert msgs[0].kind == "response"
    assert len(msgs[0].parts) == 2
    assert isinstance(msgs[0].parts[0], ThinkingPart)
    assert msgs[0].parts[0].content == "some reasoning"
    assert isinstance(msgs[0].parts[1], TextPart)
    assert msgs[0].parts[1].content == "answer"


def test_done_event_serializes_usage_tokens() -> None:
    event = DoneEvent(
        content="réponse",
        input_tokens=42,
        output_tokens=7,
        total_tokens=49,
    )

    assert event.model_dump() == {
        "type": "done",
        "content": "réponse",
        "input_tokens": 42,
        "output_tokens": 7,
        "total_tokens": 49,
    }


# --- map_model_stream_events -----------------------------------------------


async def _collect_stream_events(events: list[Any]) -> list[Any]:
    async def _fake_stream() -> Any:
        for event in events:
            yield event

    return [event async for event in map_model_stream_events(_fake_stream())]


async def test_map_model_stream_events_thinking_and_text() -> None:
    events = [
        PartStartEvent(index=0, part=ThinkingPart(content="")),
        PartDeltaEvent(index=0, delta=ThinkingPartDelta(content_delta="Hello ")),
        PartDeltaEvent(index=0, delta=ThinkingPartDelta(content_delta="world")),
        PartEndEvent(index=0, part=ThinkingPart(content="Hello world")),
        PartStartEvent(index=1, part=TextPart(content="")),
        PartDeltaEvent(index=1, delta=TextPartDelta(content_delta="Answer")),
    ]
    mapped = await _collect_stream_events(events)

    assert mapped == [
        ThinkingStartEvent(thinking_id="think-0"),
        ThinkingDeltaEvent(thinking_id="think-0", content="Hello "),
        ThinkingDeltaEvent(thinking_id="think-0", content="world"),
        ThinkingEndEvent(thinking_id="think-0"),
        TokenEvent(content="Answer"),
    ]


async def test_map_model_stream_events_first_chunk_embedded_in_part_start() -> None:
    """Régression : le premier chunk texte/thinking vit dans le PartStartEvent.

    pydantic-ai embarque le contenu du premier delta dans le `PartStartEvent`
    (cf. `ModelResponsePartsManager.handle_text_delta` / `handle_thinking_delta`).
    Sans relayage, le début de la réponse et du raisonnement disparaissaient du
    flux SSE (ex. "4" manquant à "2+2 = ?", "Je " manquant à "Je vais bien").
    """
    events = [
        PartStartEvent(index=0, part=ThinkingPart(content="je calcule ")),
        PartDeltaEvent(index=0, delta=ThinkingPartDelta(content_delta="2+2")),
        PartEndEvent(index=0, part=ThinkingPart(content="je calcule 2+2")),
        PartStartEvent(index=1, part=TextPart(content="4")),
        PartDeltaEvent(index=1, delta=TextPartDelta(content_delta="! 😄")),
    ]
    mapped = await _collect_stream_events(events)

    assert mapped == [
        ThinkingStartEvent(thinking_id="think-0"),
        ThinkingDeltaEvent(thinking_id="think-0", content="je calcule "),
        ThinkingDeltaEvent(thinking_id="think-0", content="2+2"),
        ThinkingEndEvent(thinking_id="think-0"),
        TokenEvent(content="4"),
        TokenEvent(content="! 😄"),
    ]



# --- coerce_tool_result ----------------------------------------------------


def test_coerce_tool_result_dict_passthrough() -> None:
    assert coerce_tool_result({"a": 1}) == {"a": 1}


def test_coerce_tool_result_none() -> None:
    assert coerce_tool_result(None) == {}


def test_coerce_tool_result_string_json() -> None:
    assert coerce_tool_result('{"x": 2}') == {"x": 2}


def test_coerce_tool_result_string_plain() -> None:
    assert coerce_tool_result("boom") == {"content": "boom"}


def test_coerce_tool_result_other() -> None:
    assert coerce_tool_result(42) == {"content": "42"}


# --- AgentLoop integration (TestModel) -------------------------------------


async def test_agent_loop_successful_tool_call(fake_project_client: FakeProjectClient) -> None:
    # TestModel(seed=0) appelle read_document avec document_id="a".
    fake_project_client._documents = {"a": "contenu du document A"}
    loop = _new_loop(fake_project_client)
    events = await _run(loop, _make_request())

    types = _event_types(events)
    assert ToolCallStartEvent.__name__ in types
    assert ToolCallResultEvent.__name__ in types

    read_results = [
        e for e in events
        if isinstance(e, ToolCallResultEvent) and e.tool_name == "read_document"
    ]
    assert read_results, "read_document tool result expected"
    assert all(not e.is_error for e in read_results)
    assert any("contenu du document A" in str(e.result) for e in read_results)

    start_events = [
        e for e in events
        if isinstance(e, ToolCallStartEvent) and e.tool_name == "read_document"
    ]
    assert start_events
    assert start_events[0].human_summary.startswith("Je vais lire")
    assert read_results[0].human_summary.startswith("J'ai lu")

    # Le run se termine (done ou error), sans exception non gérée.
    assert isinstance(events[-1], (DoneEvent, ErrorEvent))


async def test_agent_loop_tool_failure_surfaces_is_error() -> None:
    # Aucun document -> read_document lève FileNotFoundError -> ModelRetry -> is_error.
    client = FakeProjectClient(documents={})
    loop = _new_loop(client)
    events = await _run(loop, _make_request())

    read_results = [
        e for e in events
        if isinstance(e, ToolCallResultEvent) and e.tool_name == "read_document"
    ]
    assert read_results, "read_document tool result expected"
    assert any(e.is_error for e in read_results)
    # Le run se termine malgré l'échec outil.
    assert isinstance(events[-1], (DoneEvent, ErrorEvent))


async def test_agent_loop_max_iterations_terminates(fake_project_client: FakeProjectClient) -> None:
    loop = _new_loop(fake_project_client, max_iterations=1)
    events = await _run(loop, _make_request())
    # Avec 1 seule requête modèle autorisée, le run doit se terminer proprement.
    assert isinstance(events[-1], (DoneEvent, ErrorEvent))
