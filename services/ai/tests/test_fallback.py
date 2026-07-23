"""Tests du repli provider chat (fallback)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    InternalServerError,
    PermissionDeniedError,
    RateLimitError,
)
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.messages import TextPart, ThinkingPart, ToolCallPart
from pydantic_ai.models.test import TestModel

import app.auth as authmod
import app.main as mainmod
from app.agent.loop import AgentLoop, to_model_messages
from app.agent.tools import build_agent
from app.llm.fallback import FallbackableProviderError, is_fallbackable
from app.llm.provider_sets import resolve_fallback_chat_config
from app.schemas import (
    AgentTurnRequest,
    ChatMessage,
    ErrorEvent,
    ProviderSet,
    ThinkingStartEvent,
    TokenEvent,
    ToolCall,
    ToolCallStartEvent,
)
from app.sandbox.runner import SandboxRunner

from conftest import FakeProjectClient


def _httpx_request() -> httpx.Request:
    return httpx.Request("POST", "http://example.test/v1/chat/completions")


def _httpx_response(status: int) -> httpx.Response:
    return httpx.Response(status, request=_httpx_request())


def _sse_events(resp: Any) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    event_type: str | None = None
    data: str | None = None
    for line in resp.iter_lines():
        if line.startswith("event:"):
            event_type = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data = line[len("data:") :].strip()
        elif line == "" and event_type and data:
            events.append((event_type, json.loads(data)))
            event_type = None
            data = None
    if event_type and data:
        events.append((event_type, json.loads(data)))
    return events


def _provider_set_with_fallback() -> dict[str, Any]:
    return {
        "id": "test-fallback",
        "chat": {
            "provider": "mistral",
            "model": "mistral-small-latest",
            "api_key": "primary-key",
        },
        "chat_fallback": {
            "provider": "ollama",
            "model": "llama3.2",
        },
    }


@pytest.mark.parametrize(
    ("exc", "expected_ok", "expected_reason"),
    [
        (APITimeoutError(request=_httpx_request()), True, "timeout"),
        (APIConnectionError(request=_httpx_request()), True, "connection"),
        (
            InternalServerError(
                "server error",
                response=_httpx_response(500),
                body=None,
            ),
            True,
            "http_5xx",
        ),
        (
            RateLimitError(
                "rate limited",
                response=_httpx_response(429),
                body=None,
            ),
            True,
            "http_429",
        ),
        (httpx.TimeoutException("timeout"), True, "timeout"),
        (httpx.ConnectError("connection refused"), True, "connection"),
        (httpx.RemoteProtocolError("bad protocol"), True, "connection"),
        (
            AuthenticationError(
                "unauthorized",
                response=_httpx_response(401),
                body=None,
            ),
            False,
            "",
        ),
        (
            PermissionDeniedError(
                "forbidden",
                response=_httpx_response(403),
                body=None,
            ),
            False,
            "",
        ),
        (UsageLimitExceeded("limit"), False, ""),
        (UnexpectedModelBehavior("bad response"), False, ""),
        (ValueError("business"), False, ""),
        (asyncio.CancelledError(), False, ""),
    ],
)
def test_is_fallbackable(
    exc: BaseException,
    expected_ok: bool,
    expected_reason: str,
) -> None:
    ok, reason = is_fallbackable(exc)
    assert ok is expected_ok
    assert reason == expected_reason


def test_is_fallbackable_walks_cause_chain() -> None:
    root = APITimeoutError(request=_httpx_request())
    wrapped = RuntimeError("wrapped")
    wrapped.__cause__ = root
    ok, reason = is_fallbackable(wrapped)
    assert ok is True
    assert reason == "timeout"


def test_is_fallbackable_non_fallbackable_context_short_circuits() -> None:
    exc = UsageLimitExceeded("limit")
    exc.__context__ = httpx.ConnectError("connection refused")
    ok, reason = is_fallbackable(exc)
    assert ok is False
    assert reason == ""


def test_to_model_messages_strip_thinking() -> None:
    history = [
        ChatMessage(
            role="assistant",
            thinking="secret reasoning",
            content="visible answer",
            tool_calls=[
                ToolCall(id="tc1", name="read_document", arguments={"document_id": "a"})
            ],
        )
    ]
    msgs = to_model_messages(history, strip_thinking=True)
    parts = msgs[0].parts
    assert not any(isinstance(part, ThinkingPart) for part in parts)
    assert any(isinstance(part, TextPart) for part in parts)
    assert any(isinstance(part, ToolCallPart) for part in parts)


def test_resolve_fallback_chat_config_reuses_primary_key() -> None:
    provider_set = ProviderSet.model_validate(_provider_set_with_fallback())
    cfg = resolve_fallback_chat_config(provider_set)
    assert cfg is not None
    assert cfg.provider == "ollama"
    assert cfg.model == "llama3.2"


async def test_run_turn_fallbackable_before_emit_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Monkeypatch _iter_model_stream : échec avant tout token -> repli possible."""

    async def fail_stream(
        self: AgentLoop, node: Any, ctx: Any, *, model_round: int = 0
    ) -> AsyncIterator[Any]:
        raise APITimeoutError(request=_httpx_request())
        yield  # pragma: no cover

    monkeypatch.setattr(AgentLoop, "_iter_model_stream", fail_stream)

    loop = AgentLoop(
        agent=build_agent(TestModel(seed=0, call_tools=[])),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=10),
        max_iterations=6,
    )
    request = AgentTurnRequest(
        tenant_id="t",
        project_id="p",
        session_id="s",
        message="hello",
        documents=[],
    )

    with pytest.raises(FallbackableProviderError) as exc_info:
        async for _event in loop.run_turn(request, turn_id="turn-fb"):
            pass

    assert exc_info.value.reason == "timeout"


async def test_run_turn_fallbackable_mid_stream_yields_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def emit_then_fail(
        self: AgentLoop, node: Any, ctx: Any, *, model_round: int = 0
    ) -> AsyncIterator[Any]:
        yield TokenEvent(content="partial")
        raise APITimeoutError(request=_httpx_request())

    monkeypatch.setattr(AgentLoop, "_iter_model_stream", emit_then_fail)

    loop = AgentLoop(
        agent=build_agent(TestModel(seed=0, call_tools=[])),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=10),
        max_iterations=6,
    )
    request = AgentTurnRequest(
        tenant_id="t",
        project_id="p",
        session_id="s",
        message="hello",
        documents=[],
    )
    events = [event async for event in loop.run_turn(request, turn_id="turn-mid")]

    assert any(isinstance(event, TokenEvent) for event in events)
    error_events = [event for event in events if isinstance(event, ErrorEvent)]
    assert len(error_events) == 1
    assert error_events[0].code == "provider_unavailable"


async def test_run_turn_tool_call_blocks_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Monkeypatch _iter_tool_stream : tool_call_start sans token -> pas de repli."""

    async def tool_start_then_fail(
        self: AgentLoop,
        node: Any,
        ctx: Any,
        *,
        locale: str,
        work_id: str,
        hook_payload_base: dict[str, Any] | None = None,
        plugin_data_dir: Path | None = None,
    ) -> AsyncIterator[Any]:
        _ = work_id
        yield ToolCallStartEvent(
            tool_call_id="tc1",
            tool_name="read_document",
            arguments={"document_id": "a"},
        )
        raise APITimeoutError(request=_httpx_request())

    monkeypatch.setattr(AgentLoop, "_iter_tool_stream", tool_start_then_fail)

    loop = AgentLoop(
        agent=build_agent(TestModel(seed=0, call_tools=[])),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=10),
        max_iterations=6,
    )
    request = AgentTurnRequest(
        tenant_id="t",
        project_id="p",
        session_id="s",
        message="hello",
        documents=[],
    )
    events = [event async for event in loop.run_turn(request, turn_id="turn-tool")]

    assert any(isinstance(event, ToolCallStartEvent) for event in events)
    error_events = [event for event in events if isinstance(event, ErrorEvent)]
    assert len(error_events) == 1
    assert error_events[0].code == "provider_unavailable"


async def test_run_turn_thinking_start_counts_as_emitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ThinkingStartEvent seul (sans delta) bloque le repli provider."""

    async def thinking_start_then_fail(
        self: AgentLoop, node: Any, ctx: Any, *, model_round: int = 0
    ) -> AsyncIterator[Any]:
        yield ThinkingStartEvent(thinking_id="think-0")
        raise APITimeoutError(request=_httpx_request())

    monkeypatch.setattr(AgentLoop, "_iter_model_stream", thinking_start_then_fail)

    loop = AgentLoop(
        agent=build_agent(TestModel(seed=0, call_tools=[])),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=10),
        max_iterations=6,
    )
    request = AgentTurnRequest(
        tenant_id="t",
        project_id="p",
        session_id="s",
        message="hello",
        documents=[],
    )
    events = [event async for event in loop.run_turn(request, turn_id="turn-think")]

    assert any(isinstance(event, ThinkingStartEvent) for event in events)
    error_events = [event for event in events if isinstance(event, ErrorEvent)]
    assert len(error_events) == 1
    assert error_events[0].code == "provider_unavailable"


def test_agent_turn_fallback_success(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)
    monkeypatch.setattr(
        mainmod,
        "build_model",
        lambda config: TestModel(seed=0, call_tools=[]),
    )

    original = AgentLoop._iter_model_stream
    call_count = {"n": 0}

    async def patched_stream(
        self: AgentLoop, node: Any, ctx: Any, *, model_round: int = 0
    ) -> AsyncIterator[Any]:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise APITimeoutError(request=_httpx_request())
        async for event in original(self, node, ctx, model_round=model_round):
            yield event

    monkeypatch.setattr(AgentLoop, "_iter_model_stream", patched_stream)

    payload = {
        "tenant_id": "t",
        "project_id": str(tmp_path),
        "project_path": str(tmp_path),
        "session_id": "s-fallback",
        "message": "hello",
        "history": [],
        "documents": [],
        "provider_set": _provider_set_with_fallback(),
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

    event_types = [event_type for event_type, _data in events]
    assert event_types.count("compaction") == 0
    assert "fallback" in event_types
    fallback_data = next(data for etype, data in events if etype == "fallback")
    assert fallback_data["from_provider"] == "mistral"
    assert fallback_data["to_provider"] == "ollama"
    assert fallback_data["from_model"] == "mistral-small-latest"
    assert fallback_data["to_model"] == "llama3.2"
    assert fallback_data["reason"] == "timeout"
    assert "done" in event_types
    assert call_count["n"] >= 2


def test_agent_turn_mid_stream_no_fallback(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)
    monkeypatch.setattr(
        mainmod,
        "build_model",
        lambda config: TestModel(seed=0, call_tools=[]),
    )

    async def emit_then_fail(
        self: AgentLoop, node: Any, ctx: Any, *, model_round: int = 0
    ) -> AsyncIterator[Any]:
        yield TokenEvent(content="partial")
        raise APITimeoutError(request=_httpx_request())

    monkeypatch.setattr(AgentLoop, "_iter_model_stream", emit_then_fail)

    payload = {
        "tenant_id": "t",
        "project_id": str(tmp_path),
        "project_path": str(tmp_path),
        "session_id": "s-mid",
        "message": "hello",
        "history": [],
        "documents": [],
        "provider_set": _provider_set_with_fallback(),
    }

    with TestClient(mainmod.app) as client:
        with client.stream(
            "POST",
            "/agent/turn",
            json=payload,
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        ) as resp:
            events = _sse_events(resp)

    event_types = [event_type for event_type, _data in events]
    assert "token" in event_types
    assert "fallback" not in event_types
    error_data = next(data for etype, data in events if etype == "error")
    assert error_data["code"] == "provider_unavailable"


def test_agent_turn_no_fallback_configured(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)
    monkeypatch.setattr(
        mainmod,
        "build_model",
        lambda config: TestModel(seed=0, call_tools=[]),
    )

    async def fail_stream(
        self: AgentLoop, node: Any, ctx: Any, *, model_round: int = 0
    ) -> AsyncIterator[Any]:
        raise APITimeoutError(request=_httpx_request())
        yield  # pragma: no cover

    monkeypatch.setattr(AgentLoop, "_iter_model_stream", fail_stream)

    payload = {
        "tenant_id": "t",
        "project_id": str(tmp_path),
        "project_path": str(tmp_path),
        "session_id": "s-no-fb",
        "message": "hello",
        "history": [],
        "documents": [],
        "provider_set": {
            "id": "no-fallback",
            "chat": {
                "provider": "mistral",
                "model": "mistral-small-latest",
                "api_key": "primary-key",
            },
        },
    }

    with TestClient(mainmod.app) as client:
        with client.stream(
            "POST",
            "/agent/turn",
            json=payload,
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        ) as resp:
            events = _sse_events(resp)

    event_types = [event_type for event_type, _data in events]
    assert "fallback" not in event_types
    error_data = next(data for etype, data in events if etype == "error")
    assert error_data["code"] == "provider_unavailable"


def test_agent_turn_fallback_also_fails(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)
    monkeypatch.setattr(
        mainmod,
        "build_model",
        lambda config: TestModel(seed=0, call_tools=[]),
    )

    async def always_fail(
        self: AgentLoop, node: Any, ctx: Any, *, model_round: int = 0
    ) -> AsyncIterator[Any]:
        raise RateLimitError(
            "rate limited",
            response=_httpx_response(429),
            body=None,
        )
        yield  # pragma: no cover

    monkeypatch.setattr(AgentLoop, "_iter_model_stream", always_fail)

    payload = {
        "tenant_id": "t",
        "project_id": str(tmp_path),
        "project_path": str(tmp_path),
        "session_id": "s-fb-fail",
        "message": "hello",
        "history": [],
        "documents": [],
        "provider_set": _provider_set_with_fallback(),
    }

    with TestClient(mainmod.app) as client:
        with client.stream(
            "POST",
            "/agent/turn",
            json=payload,
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        ) as resp:
            events = _sse_events(resp)

    event_types = [event_type for event_type, _data in events]
    assert event_types.count("fallback") == 1
    assert "done" not in event_types
    error_data = next(data for etype, data in events if etype == "error")
    assert error_data["code"] == "provider_unavailable"
