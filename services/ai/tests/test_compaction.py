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
    estimate_history_tokens,
)
from app.config import get_settings
from app.schemas import ChatMessage, UtilitySummarizeResponse

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
    # L'estimation compte contenu + thinking + overhead de rôle (len(role)+2)
    # par message, puis applique chars/4.
    # user  : "abcd" (4) + "user" (4) + 2 = 10
    # assistant : "abcdefgh" (8) + "assistant" (9) + 2 = 19
    # total = 29 chars ; 29 // 4 = 7.
    assert estimate_history_tokens(
        [
            ChatMessage(role="user", content="abcd"),
            ChatMessage(role="assistant", thinking="abcdefgh"),
        ]
    ) == 7


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
    assert compacted[0].role == "system"
    assert "Résumé" in (compacted[0].content or "")
    assert compacted[1:] == history[-COMPACT_KEEP_LAST:]
    assert event.kept_count == COMPACT_KEEP_LAST
    assert event.dropped_count == len(history) - COMPACT_KEEP_LAST
    assert event.truncated is False
    assert event.summary_tokens == 42


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
