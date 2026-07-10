import json
from typing import Any

from app.config import Settings
from app.llm.utility import summarize_conversation
from app.schemas import (
    ChatMessage,
    CompactionEvent,
    LLMProviderConfig,
    UtilitySummarizeRequest,
)


def _message_char_estimate(message: ChatMessage) -> int:
    """Heuristique de taille d'un message pour l'estimation de tokens.

    Compte le contenu texte, le thinking, les métadonnées de rôle et les
    payloads d'outils (tool_calls sérialisés). Pas de tokenizer provider ici :
    on applique chars/4 comme approximation conservative (sous-estime rarement
    le coût structurel JSON).
    """
    total = len(message.content or "") + len(message.thinking or "")
    total += len(message.name or "") + len(message.tool_call_id or "")
    for tool_call in message.tool_calls:
        total += len(tool_call.id) + len(tool_call.name)
        total += len(json.dumps(tool_call.arguments, ensure_ascii=False))
    total += len(message.role) + 2
    return total


def estimate_history_tokens(history: list[ChatMessage]) -> int:
    total_chars = sum(_message_char_estimate(message) for message in history)
    return max(total_chars // 4, 0)


async def compact_history_if_needed(
    history: list[ChatMessage],
    context_window: int | None,
    auto_compact: bool,
    chat_config: LLMProviderConfig | None,
    settings: Settings | Any,
) -> tuple[list[ChatMessage], CompactionEvent | None]:
    keep_last = settings.compaction_keep_messages
    min_history = settings.compaction_min_history
    min_old = settings.compaction_min_old
    threshold = settings.compaction_usage_threshold
    fallback_keep = settings.compaction_fallback_keep_messages

    if not context_window or not auto_compact or len(history) < min_history:
        return history, None

    estimate = estimate_history_tokens(history)
    if estimate < int(threshold * context_window):
        return history, None

    old = history[:-keep_last]
    recent = history[-keep_last:]
    if len(old) < min_old:
        return history, None

    try:
        req = UtilitySummarizeRequest(
            messages=old,
            llm_provider_config=chat_config,
            utility_llm_config=None,
            focus=(
                "Conserve les décisions, fichiers concernés et questions ouvertes "
                "pour la suite du travail."
            ),
        )
        resp = await summarize_conversation(req, settings)
        summary_msg = ChatMessage(
            role="system",
            content=f"Résumé des échanges précédents :\n\n{resp.summary}",
        )
        return (
            [summary_msg] + recent,
            CompactionEvent(
                dropped_count=len(old),
                kept_count=len(recent),
                summary_tokens=resp.input_tokens,
                truncated=False,
                summary_failed=False,
            ),
        )
    except Exception:
        # Fallback : conserver les N derniers messages intermédiaires plutôt que tout jeter.
        intermediate = old[-fallback_keep:] if fallback_keep > 0 else []
        kept = intermediate + recent
        return (
            kept,
            CompactionEvent(
                dropped_count=len(old) - len(intermediate),
                kept_count=len(kept),
                summary_tokens=None,
                truncated=True,
                summary_failed=True,
            ),
        )
