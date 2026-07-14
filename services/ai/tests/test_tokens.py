from __future__ import annotations

import json
import math

from app.agent.compaction import estimate_history_tokens
from app.llm.tokens import estimate_message_tokens, estimate_tokens
from app.schemas import ChatMessage, ToolCall


def test_estimate_tokens_empty() -> None:
    assert estimate_tokens("") == 0


def test_estimate_tokens_latin_exact() -> None:
    assert estimate_tokens("abcd") == math.ceil(4 / 3) == 2


def test_estimate_tokens_cjk_conservative() -> None:
    cjk_text = "你好世界"
    latin_text = "abcd"
    assert len(cjk_text) == len(latin_text)
    cjk_tokens = estimate_tokens(cjk_text)
    latin_tokens = estimate_tokens(latin_text)
    assert cjk_tokens >= len(cjk_text)
    assert cjk_tokens > latin_tokens


def test_estimate_message_tokens_dense_json_tool_call() -> None:
    dense_args = {
        "items": [{"id": i, "value": "x" * 20} for i in range(10)],
        "nested": {"a": 1, "b": [1, 2, 3]},
    }
    message = ChatMessage(
        role="assistant",
        content="",
        tool_calls=[
            ToolCall(
                id="call_dense_json",
                name="search_documents",
                arguments=dense_args,
            )
        ],
    )
    new_estimate = estimate_message_tokens(message)
    parts = [
        "",
        "",
        "",
        "",
        "assistant",
        "call_dense_json",
        "search_documents",
        json.dumps(dense_args, ensure_ascii=False),
    ]
    old_chars_estimate = sum(len(part) for part in parts) // 4
    assert new_estimate >= old_chars_estimate


def test_estimate_history_tokens_deterministic_non_negative() -> None:
    history = [
        ChatMessage(role="user", content="hello"),
        ChatMessage(role="assistant", content="world"),
    ]
    first = estimate_history_tokens(history)
    second = estimate_history_tokens(history)
    assert first == second
    assert first >= 0
