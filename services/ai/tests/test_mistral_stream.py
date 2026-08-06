"""Tests unitaires du parsing du format chunk-list Mistral (sans réseau)."""

from __future__ import annotations

from pydantic_ai._parts_manager import ModelResponsePartsManager
from pydantic_ai.messages import (
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
)
from pydantic_ai.models import ModelRequestParameters

from app.llm.mistral import _extract_thinking_text, iter_mistral_chunk_events


def _make_parts_manager() -> ModelResponsePartsManager:
    return ModelResponsePartsManager(model_request_parameters=ModelRequestParameters())


def test_extract_thinking_text_concatenates_inner_text_chunks() -> None:
    thinking = [
        {"type": "text", "text": "Hello "},
        {"type": "text", "text": "world"},
    ]
    assert _extract_thinking_text(thinking) == "Hello world"
    assert _extract_thinking_text(None) == ""
    assert _extract_thinking_text("not a list") == ""
    assert _extract_thinking_text([{"type": "text"}]) == ""


def test_iter_mistral_chunk_events_maps_thinking_then_text() -> None:
    pm = _make_parts_manager()
    content = [
        {"type": "thinking", "thinking": [{"type": "text", "text": "Réflexion "}]},
    ]

    events = list(iter_mistral_chunk_events(content, pm, provider_name="mistral"))

    assert len(events) == 1
    start = events[0]
    assert isinstance(start, PartStartEvent)
    assert isinstance(start.part, ThinkingPart)
    assert start.part.content == "Réflexion "


def test_iter_mistral_chunk_events_accumulates_thinking_deltas() -> None:
    pm = _make_parts_manager()

    list(iter_mistral_chunk_events(
        [{"type": "thinking", "thinking": [{"type": "text", "text": "abc"}]}],
        pm,
        "mistral",
    ))
    events = list(iter_mistral_chunk_events(
        [{"type": "thinking", "thinking": [{"type": "text", "text": "def"}]}],
        pm,
        "mistral",
    ))

    assert len(events) == 1
    delta = events[0]
    assert isinstance(delta, PartDeltaEvent)
    assert isinstance(delta.delta, ThinkingPartDelta)
    assert delta.delta.content_delta == "def"


def test_iter_mistral_chunk_events_maps_text_chunk() -> None:
    pm = _make_parts_manager()

    events = list(iter_mistral_chunk_events(
        [{"type": "text", "text": "Réponse"}],
        pm,
        "mistral",
    ))

    assert len(events) == 1
    start = events[0]
    assert isinstance(start, PartStartEvent)
    assert isinstance(start.part, TextPart)
    assert start.part.content == "Réponse"


def test_iter_mistral_chunk_events_transition_chunk_has_thinking_close_and_text_start() -> None:
    pm = _make_parts_manager()
    # Phase de réflexion initiale.
    list(iter_mistral_chunk_events(
        [{"type": "thinking", "thinking": [{"type": "text", "text": "je calcule"}]}],
        pm,
        "mistral",
    ))
    # Chunk de transition : ThinkChunk fermé + premier TextChunk.
    events = list(iter_mistral_chunk_events(
        [
            {"type": "thinking", "thinking": [], "closed": True},
            {"type": "text", "text": "391"},
        ],
        pm,
        "mistral",
    ))

    # Le thinking vide ne produit rien ; le text démarre une nouvelle part.
    assert len(events) == 1
    assert isinstance(events[0], PartStartEvent)
    assert isinstance(events[0].part, TextPart)
    assert events[0].part.content == "391"


def test_iter_mistral_chunk_events_ignores_non_list_content() -> None:
    pm = _make_parts_manager()
    assert list(iter_mistral_chunk_events("plain string", pm, "mistral")) == []
    assert list(iter_mistral_chunk_events(None, pm, "mistral")) == []


def test_iter_mistral_chunk_events_ignores_unknown_chunk_types() -> None:
    pm = _make_parts_manager()
    events = list(iter_mistral_chunk_events(
        [{"type": "unknown", "data": "x"}, {"type": "text", "text": "ok"}],
        pm,
        "mistral",
    ))
    assert len(events) == 1
    assert isinstance(events[0].part, TextPart)


def test_normalize_mistral_content_list_extracts_thinking_and_text() -> None:
    from app.llm.mistral import MistralChatModel, normalize_mistral_content_list

    content = [
        {"type": "thinking", "thinking": [{"type": "text", "text": "Réfléchis "}]},
        {"type": "text", "text": "Réponse"},
    ]
    response_text, thinking = normalize_mistral_content_list(content)
    assert response_text == "Réponse"
    assert thinking == "Réfléchis"

    class _FakeChoice:
        def __init__(self) -> None:
            self.message = type(
                "Message",
                (),
                {
                    "content": content,
                    "model_dump": lambda self: {
                        "content": content,
                        "role": "assistant",
                    },
                },
            )()

    class _FakeResponse:
        def __init__(self) -> None:
            self.choices = [_FakeChoice()]

        def model_dump(self) -> dict:
            return {
                "id": "cmpl-test",
                "object": "chat.completion",
                "created": 0,
                "model": "mistral-large",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": content,
                        },
                        "finish_reason": "stop",
                    }
                ],
            }

    validated = MistralChatModel._validate_completion(object(), _FakeResponse())  # type: ignore[arg-type]
    assert validated.choices[0].message.content == "Réponse"
    assert validated.choices[0].message.reasoning_content == "Réfléchis"
