from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.models.test import TestModel

import app.agent.compaction as compactionmod
import app.auth as authmod
import app.main as mainmod
from app.agent.compaction import (
    compact_history_if_needed,
    estimate_documents_overhead,
    estimate_history_tokens,
    estimate_memory_overhead,
)
from app.config import get_settings
from app.i18n import t
from app.schemas import ChatMessage, DocumentReference, UtilitySummarizeRequest, UtilitySummarizeResponse

COMPACT_KEEP_LAST = get_settings().compaction_keep_messages
COMPACT_MIN_HISTORY = get_settings().compaction_min_history


def _history(count: int, *, content: str = "message content") -> list[ChatMessage]:
    return [
        ChatMessage(
            role="user" if index % 2 == 0 else "assistant",
            content=f"{content} {index}",
        )
        for index in range(count)
    ]


def _sse_events(resp: Any) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    event_type: str | None = None
    data: str | None = None
    for line in resp.iter_lines():
        if line.startswith("event:"):
            event_type = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data = line[len("data:"):].strip()
        elif line == "" and event_type and data:
            events.append((event_type, json.loads(data)))
            event_type = None
            data = None
    if event_type and data:
        events.append((event_type, json.loads(data)))
    return events


def test_estimate_history_tokens() -> None:
    assert estimate_history_tokens([]) == 0
    # L'estimation assemble content/thinking/name/tool_call_id/role par message
    # (join \n), puis applique l'heuristique conservative : CJK ~1 token/char,
    # autres caracteres ceil(chars/3).
    # user      : "abcd\n\n\n\nuser" -> ceil(12/3) = 4
    # assistant : "\nabcdefgh\n\n\nassistant" -> ceil(21/3) = 7
    # total = 11 (ancien chars/4 donnait 7).
    assert estimate_history_tokens(
        [
            ChatMessage(role="user", content="abcd"),
            ChatMessage(role="assistant", thinking="abcdefgh"),
        ]
    ) == 11


async def test_compact_history_under_threshold_returns_original() -> None:
    history = _history(COMPACT_MIN_HISTORY, content="short")

    compacted, event = await compact_history_if_needed(
        history,
        context_window=10_000,
        auto_compact=True,
        chat_config=None,
        settings=get_settings(),
    )

    assert compacted is history
    assert event is None


async def test_compact_history_summarizes_old_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = _history(10, content="x" * 80)

    async def fake_summarize(*_args: Any, **_kwargs: Any) -> UtilitySummarizeResponse:
        return UtilitySummarizeResponse(
            summary="Décision conservée",
            input_tokens=42,
            output_tokens=10,
        )

    monkeypatch.setattr(compactionmod, "summarize_conversation", fake_summarize)

    compacted, event = await compact_history_if_needed(
        history,
        context_window=100,
        auto_compact=True,
        chat_config=None,
        settings=get_settings(),
    )

    assert event is not None
    assert compacted[0].role == "user"
    assert "Résumé" in (compacted[0].content or "")
    assert compacted[1:] == history[-COMPACT_KEEP_LAST:]
    assert event.kept_count == COMPACT_KEEP_LAST
    assert event.dropped_count == len(history) - COMPACT_KEEP_LAST
    assert event.truncated is False
    assert event.summary_tokens == 42
    assert event.summary == "Décision conservée"


async def test_compact_history_overhead_triggers_compaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = _history(COMPACT_MIN_HISTORY, content="short")

    async def fake_summarize(*_args: Any, **_kwargs: Any) -> UtilitySummarizeResponse:
        return UtilitySummarizeResponse(summary="ok", input_tokens=1, output_tokens=1)

    monkeypatch.setattr(compactionmod, "summarize_conversation", fake_summarize)

    compacted, event = await compact_history_if_needed(
        history,
        context_window=10_000,
        auto_compact=True,
        chat_config=None,
        settings=get_settings(),
        overhead_tokens=10_000,
    )

    assert event is not None
    assert compacted[0].role == "user"


async def test_compact_history_prior_summary_incremental(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prefix = t("fr", "utility.compaction_summary_prefix")
    prior = ChatMessage(
        role="system",
        content=f"{prefix}\n\nAncien résumé conservé",
    )
    history = [prior] + _history(9, content="x" * 80)
    captured: dict[str, UtilitySummarizeRequest | None] = {"req": None}

    async def fake_summarize(
        req: UtilitySummarizeRequest, *_args: Any, **_kwargs: Any
    ) -> UtilitySummarizeResponse:
        captured["req"] = req
        return UtilitySummarizeResponse(
            summary="Résumé enrichi",
            input_tokens=10,
            output_tokens=5,
        )

    monkeypatch.setattr(compactionmod, "summarize_conversation", fake_summarize)

    compacted, event = await compact_history_if_needed(
        history,
        context_window=100,
        auto_compact=True,
        chat_config=None,
        settings=get_settings(),
    )

    assert captured["req"] is not None
    assert captured["req"].prior_summary == "Ancien résumé conservé"
    assert len(captured["req"].messages) == len(history) - COMPACT_KEEP_LAST - 1
    assert event is not None
    assert event.summary == "Résumé enrichi"
    assert "Résumé enrichi" in (compacted[0].content or "")


async def test_compact_history_prior_summary_preserved_on_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prefix = t("fr", "utility.compaction_summary_prefix")
    prior = ChatMessage(
        role="system",
        content=f"{prefix}\n\nAncien résumé conservé",
    )
    history = [prior] + _history(9, content="x" * 80)

    async def fail_summarize(*_args: Any, **_kwargs: Any) -> UtilitySummarizeResponse:
        raise RuntimeError("network down")

    monkeypatch.setattr(compactionmod, "summarize_conversation", fail_summarize)

    compacted, event = await compact_history_if_needed(
        history,
        context_window=100,
        auto_compact=True,
        chat_config=None,
        settings=get_settings(),
    )

    assert event is not None
    assert event.summary_failed is True
    assert event.summary is None
    assert compacted[0] == prior


def test_estimate_memory_overhead(tmp_path) -> None:
    from app.memory_stores import open_memory_store_for_scope

    store = open_memory_store_for_scope("project", tmp_path)
    try:
        store.add_memory(content="souvenir test", source="test")
    finally:
        store.close()

    overhead = estimate_memory_overhead(tmp_path)
    assert overhead > 0


def test_estimate_documents_overhead() -> None:
    docs = [
        DocumentReference(
            id="doc-1",
            name="rapport.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            metadata={"relativePath": "docs/rapport.pdf", "kind": "pdf"},
        )
    ]
    assert estimate_documents_overhead(docs) > 0
    assert estimate_documents_overhead([]) == 0


def test_estimate_documents_overhead_counts_base64() -> None:
    docs = [
        DocumentReference(
            id="att-1",
            name="image.png",
            mime_type="image/png",
            content_base64="A" * 4000,
            metadata={"source": "chat-attachment"},
        )
    ]
    without_base64 = DocumentReference(
        id="att-1",
        name="image.png",
        mime_type="image/png",
        size_bytes=3000,
        metadata={"source": "chat-attachment"},
    )
    assert estimate_documents_overhead(docs) > estimate_documents_overhead(
        [without_base64]
    )


def test_extract_prior_summary_accepts_front_persisted_format() -> None:
    """Le format persisté par le front doit être reconnu pour le résumé incrémental."""
    from app.agent.compaction import _extract_prior_summary

    prefix = t("fr", "utility.compaction_summary_prefix")
    # Même format que applyCompactionToMessages : prefixI18n + summary
    front_content = f"{prefix}\n\nDécision persistée côté client"
    message = ChatMessage(role="user", content=front_content)

    prior, prior_msg, remaining = _extract_prior_summary([message], "fr")

    assert prior == "Décision persistée côté client"
    assert prior_msg == message
    assert remaining == []


def test_extract_prior_summary_accepts_legacy_system_role() -> None:
    from app.agent.compaction import _extract_prior_summary

    prefix = t("fr", "utility.compaction_summary_prefix")
    message = ChatMessage(
        role="system",
        content=f"{prefix}\n\nAncien résumé legacy",
    )

    prior, prior_msg, remaining = _extract_prior_summary([message], "fr")

    assert prior == "Ancien résumé legacy"
    assert prior_msg == message
    assert remaining == []


async def test_compact_history_too_few_messages_returns_original() -> None:
    history = _history(COMPACT_MIN_HISTORY - 1, content="x" * 200)

    compacted, event = await compact_history_if_needed(
        history,
        context_window=10,
        auto_compact=True,
        chat_config=None,
        settings=get_settings(),
    )

    assert compacted is history
    assert event is None


async def test_compact_history_summarize_failure_truncates_recent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = _history(10, content="x" * 80)

    async def fail_summarize(*_args: Any, **_kwargs: Any) -> UtilitySummarizeResponse:
        raise RuntimeError("network down")

    monkeypatch.setattr(compactionmod, "summarize_conversation", fail_summarize)

    settings = get_settings()
    compacted, event = await compact_history_if_needed(
        history,
        context_window=100,
        auto_compact=True,
        chat_config=None,
        settings=settings,
    )

    fallback_keep = settings.compaction_fallback_keep_messages
    expected_intermediate = history[-(COMPACT_KEEP_LAST + fallback_keep) : -COMPACT_KEEP_LAST]
    expected = expected_intermediate + history[-COMPACT_KEEP_LAST:]
    assert compacted == expected
    assert all(message.role != "system" for message in compacted)
    assert event is not None
    assert event.truncated is True
    assert event.summary_failed is True
    assert event.summary_tokens is None
    assert event.kept_count == len(expected)
    assert event.dropped_count == len(history) - len(expected)


def test_agent_turn_emits_compaction_event_first(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)
    monkeypatch.setattr(
        mainmod,
        "build_model",
        lambda config: TestModel(seed=0, call_tools=["read_document"]),
    )

    async def fake_summarize(*_args: Any, **_kwargs: Any) -> UtilitySummarizeResponse:
        return UtilitySummarizeResponse(
            summary="Décision conservée",
            input_tokens=42,
            output_tokens=10,
        )

    monkeypatch.setattr(compactionmod, "summarize_conversation", fake_summarize)
    history = [
        {"role": "user" if index % 2 == 0 else "assistant", "content": "x" * 80}
        for index in range(10)
    ]
    payload = {
        "tenant_id": "t",
        "project_id": str(tmp_path),
        "project_path": str(tmp_path),
        "session_id": "s",
        "message": "lire",
        "history": history,
        "documents": [],
        "context_window": 100,
        "auto_compact": True,
    }

    with TestClient(mainmod.app) as client:
        with client.stream(
            "POST",
            "/agent/turn",
            json=payload,
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        ) as resp:
            assert resp.status_code == 200
            events = _sse_events(resp)

    assert events
    assert events[0][0] == "turn_start"
    assert events[1][0] == "compaction"
    assert events[1][1]["dropped_count"] == len(history) - COMPACT_KEEP_LAST
    assert events[1][1]["kept_count"] == COMPACT_KEEP_LAST
    assert events[1][1]["summary_tokens"] == 42
    assert events[1][1]["truncated"] is False
    assert events[1][1]["summary"] == "Décision conservée"
