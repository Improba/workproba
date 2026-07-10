"""Modèle Mistral pour Pydantic AI.

Mistral expose le raisonnement (`reasoning_effort="high"`) via l'API OpenAI-compat,
mais en streaming le `delta.content` n'est **pas** une chaîne : c'est une liste de
chunks typés (`ThinkChunk` / `TextChunk`) durant la phase de réflexion, puis une
chaîne durant la phase de réponse. Pydantic AI 2.7.0 ne gère pas ce format
chunk-list et l'affecterait brutalement à un `TextPartDelta`.

On sous-classe donc `OpenAIChatModel` pour fournir un `OpenAIStreamedResponse`
qui mappe explicitement les chunks Mistral :

- `{'type': 'thinking', 'thinking': [{'type': 'text', 'text': ...}, ...]}`
  -> `ThinkingPart` (via `handle_thinking_delta`)
- `{'type': 'text', 'text': ...}`
  -> `TextPart` (via `handle_text_delta`)

Quand `delta.content` redevient une chaîne (phase de réponse), on délègue au
comportement standard de `OpenAIStreamedResponse`.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic_ai._parts_manager import ModelResponsePartsManager
from pydantic_ai.messages import ModelResponseStreamEvent
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIStreamedResponse

_THINKING_VENDOR_ID = "mistral-thinking"
_TEXT_VENDOR_ID = "content"


def _extract_thinking_text(thinking_field: Any) -> str:
    """Concatène le texte des `TextChunk` internes d'un `ThinkChunk` Mistral."""
    if not isinstance(thinking_field, list):
        return ""
    return "".join(
        inner.get("text", "")
        for inner in thinking_field
        if isinstance(inner, dict) and inner.get("type") == "text"
    )


def iter_mistral_chunk_events(
    content: Any,
    parts_manager: ModelResponsePartsManager,
    provider_name: str,
) -> Iterable[ModelResponseStreamEvent]:
    """Mappe un `delta.content` Mistral (chaîne ou liste de chunks) en events.

    Format chunk-list (phase de réflexion + transition) :
    - `{'type': 'thinking', 'thinking': [{'type': 'text', 'text': ...}, ...]}` -> ThinkingPart
    - `{'type': 'text', 'text': ...}` -> TextPart

    Une `str` (phase de réponse) ne produit rien ici ; elle est gérée par
    `OpenAIStreamedResponse._map_text_delta` standard.
    """
    if not isinstance(content, list):
        return
    for chunk in content:
        if not isinstance(chunk, dict):
            continue
        chunk_type = chunk.get("type")
        if chunk_type == "thinking":
            text = _extract_thinking_text(chunk.get("thinking"))
            if text:
                yield from parts_manager.handle_thinking_delta(
                    vendor_part_id=_THINKING_VENDOR_ID,
                    id=_THINKING_VENDOR_ID,
                    content=text,
                    provider_name=provider_name,
                )
        elif chunk_type == "text":
            text = chunk.get("text") or ""
            if text:
                yield from parts_manager.handle_text_delta(
                    vendor_part_id=_TEXT_VENDOR_ID,
                    content=text,
                    provider_name=provider_name,
                )


class MistralStreamedResponse(OpenAIStreamedResponse):
    """Stream Mistral gérant le format chunk-list de `reasoning_effort`."""

    def _map_text_delta(self, choice: Any) -> Iterable[ModelResponseStreamEvent]:
        content = choice.delta.content

        # Format chunk-list Mistral (phase de réflexion + transition).
        if isinstance(content, list):
            yield from iter_mistral_chunk_events(content, self._parts_manager, self.provider_name)
            return

        # Phase de réponse : `delta.content` est une chaîne standard.
        yield from super()._map_text_delta(choice)


class MistralChatModel(OpenAIChatModel):
    """`OpenAIChatModel` adapté au format de raisonnement Mistral."""

    @property
    def _streamed_response_cls(self) -> type[OpenAIStreamedResponse]:
        return MistralStreamedResponse
