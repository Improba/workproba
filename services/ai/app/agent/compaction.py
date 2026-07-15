from pathlib import Path
from typing import Any

from app.config import Settings
from app.i18n import DEFAULT_LOCALE, t
from app.llm.tokens import estimate_message_tokens, estimate_tokens
from app.llm.utility import summarize_conversation
from app.schemas import (
    ChatMessage,
    CompactionEvent,
    DocumentReference,
    LLMProviderConfig,
    UtilitySummarizeRequest,
)


def estimate_history_tokens(
    history: list[ChatMessage],
    provider: str | None = None,
) -> int:
    """Estime le cout token de l'historique avec un estimateur conservateur."""
    return max(
        sum(estimate_message_tokens(message, provider=provider) for message in history),
        0,
    )


def estimate_memory_overhead(
    data_dir: str | Path | None,
    *,
    max_items: int | None = None,
) -> int:
    """Estime le coût token des souvenirs injectés via memory_prompt."""
    if data_dir is None:
        return 0

    from app.config import get_settings
    from app.memory_stores import open_memory_store_for_scope

    if max_items is None:
        settings = get_settings()
        max_items = settings.memory_prompt_topk

    workspace_data_dir = Path(data_dir).expanduser().resolve()
    combined: list[str] = []
    for scope in ("user", "project"):
        try:
            store = open_memory_store_for_scope(scope, workspace_data_dir)
        except Exception:
            continue
        try:
            for item in store.list_memories():
                content = str(item.get("content", "")).strip()
                if content:
                    combined.append(content)
        finally:
            store.close()
    if not combined:
        return 0
    return max(estimate_tokens("\n".join(combined[:max_items])), 0)


def estimate_documents_overhead(documents: list[DocumentReference]) -> int:
    """Estime le coût token de l'inventaire documents transmis au tour."""
    if not documents:
        return 0
    parts: list[str] = []
    for doc in documents:
        parts.append(doc.id)
        parts.append(doc.name)
        parts.append(doc.mime_type or "")
        parts.append(str(doc.metadata.get("relativePath", "")))
        parts.append(str(doc.metadata.get("kind", "")))
        if doc.content_base64:
            parts.append(doc.content_base64)
        elif doc.size_bytes is not None:
            parts.append(str(doc.size_bytes))
    return max(estimate_tokens("\n".join(parts)), 0)


def _extract_prior_summary(
    old: list[ChatMessage],
    locale: str,
) -> tuple[str | None, ChatMessage | None, list[ChatMessage]]:
    """Détecte un résumé incrémental en tête de `old` et le retire de la liste."""
    if not old:
        return None, None, old

    first = old[0]
    prefix = t(locale, "utility.compaction_summary_prefix")
    content = (first.content or "").strip()
    if not content.startswith(prefix):
        return None, None, old
    if first.role not in ("system", "user"):
        return None, None, old

    body = content[len(prefix) :].strip()
    prior_summary = body or None
    return prior_summary, first, old[1:]


async def compact_history_if_needed(
    history: list[ChatMessage],
    context_window: int | None,
    auto_compact: bool,
    chat_config: LLMProviderConfig | None,
    settings: Settings | Any,
    locale: str = DEFAULT_LOCALE,
    *,
    overhead_tokens: int = 0,
) -> tuple[list[ChatMessage], CompactionEvent | None]:
    keep_last = settings.compaction_keep_messages
    min_history = settings.compaction_min_history
    min_old = settings.compaction_min_old
    threshold = settings.compaction_usage_threshold
    fallback_keep = settings.compaction_fallback_keep_messages

    if not context_window or not auto_compact or len(history) < min_history:
        return history, None

    estimate = estimate_history_tokens(
        history,
        provider=chat_config.provider if chat_config else None,
    ) + overhead_tokens
    if estimate < int(threshold * context_window):
        return history, None

    old = history[:-keep_last]
    recent = history[-keep_last:]
    if len(old) < min_old:
        return history, None

    prior_summary, prior_summary_msg, old_for_summary = _extract_prior_summary(
        old,
        locale,
    )

    try:
        compaction_config = (
            chat_config.model_copy(update={"reasoning_effort": None})
            if chat_config is not None
            else None
        )
        req = UtilitySummarizeRequest(
            messages=old_for_summary,
            llm_provider_config=compaction_config,
            utility_llm_config=None,
            focus=t(locale, "utility.compaction_focus"),
            prior_summary=prior_summary,
            locale=locale,
        )
        resp = await summarize_conversation(req, settings)
        summary_msg = ChatMessage(
            role="user",
            content=(
                f"{t(locale, 'utility.compaction_summary_prefix')}\n\n{resp.summary}"
            ),
        )
        return (
            [summary_msg] + recent,
            CompactionEvent(
                dropped_count=len(old),
                kept_count=len(recent),
                summary_tokens=resp.input_tokens,
                truncated=False,
                summary_failed=False,
                summary=resp.summary,
            ),
        )
    except Exception:
        # Fallback : conserver les N derniers messages intermédiaires plutôt que tout jeter.
        intermediate = old[-fallback_keep:] if fallback_keep > 0 else []
        if prior_summary_msg is not None:
            intermediate = [prior_summary_msg] + [
                message for message in intermediate if message is not prior_summary_msg
            ]
        kept = intermediate + recent
        return (
            kept,
            CompactionEvent(
                dropped_count=len(old) - len(intermediate),
                kept_count=len(kept),
                summary_tokens=None,
                truncated=True,
                summary_failed=True,
                summary=None,
            ),
        )
