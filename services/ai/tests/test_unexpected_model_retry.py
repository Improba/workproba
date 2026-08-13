"""Tests du retry même modèle sur UnexpectedModelBehavior."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from pydantic_ai.exceptions import ContentFilterError, UnexpectedModelBehavior
from pydantic_ai.models.test import TestModel

from app.agent.effects import tool_blocks_model_behavior_retry
from app.agent.loop import AgentLoop
from app.agent.tools import build_agent
from app.schemas import (
    AgentTurnRequest,
    DoneEvent,
    ErrorEvent,
    TokenEvent,
    ToolCallResultEvent,
)
from app.sandbox.runner import SandboxRunner

from conftest import FakeProjectClient


def _make_loop() -> AgentLoop:
    return AgentLoop(
        agent=build_agent(TestModel(seed=0, call_tools=[])),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=10),
        max_iterations=6,
    )


def _make_request() -> AgentTurnRequest:
    return AgentTurnRequest(
        tenant_id="t",
        project_id="p",
        session_id="s-retry",
        message="hello",
        documents=[],
    )


@pytest.mark.parametrize(
    ("tool_name", "is_error", "expected"),
    [
        ("read_document", False, False),
        ("list_files", False, False),
        ("managed__ihora__get_project", False, False),
        ("write_docx", False, True),
        ("generate_document", False, True),
        ("run_code", False, True),
        ("publish_artifact", False, True),
        ("browser_extract", False, False),
        ("browser_click", False, True),
        ("managed__ihora__create_task", False, True),
        ("write_docx", True, False),
    ],
)
def test_tool_blocks_model_behavior_retry(
    tool_name: str, is_error: bool, expected: bool
) -> None:
    assert tool_blocks_model_behavior_retry(tool_name, is_error=is_error) is expected


async def test_run_turn_unexpected_model_retry_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = AgentLoop._iter_model_stream
    call_count = {"n": 0}

    async def fail_then_succeed(
        self: AgentLoop, node: Any, ctx: Any, *, model_round: int = 0
    ) -> AsyncIterator[Any]:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise UnexpectedModelBehavior("bad response")
        async for event in original(self, node, ctx, model_round=model_round):
            yield event

    monkeypatch.setattr(AgentLoop, "_iter_model_stream", fail_then_succeed)

    events = [
        event
        async for event in _make_loop().run_turn(_make_request(), turn_id="turn-retry-ok")
    ]

    assert call_count["n"] >= 2
    assert any(isinstance(event, DoneEvent) for event in events)
    error_events = [event for event in events if isinstance(event, ErrorEvent)]
    assert not any(event.code == "unexpected_model_behavior" for event in error_events)


async def test_run_turn_unexpected_model_double_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_count = {"n": 0}

    async def always_fail(
        self: AgentLoop, node: Any, ctx: Any, *, model_round: int = 0
    ) -> AsyncIterator[Any]:
        call_count["n"] += 1
        raise UnexpectedModelBehavior("bad response")
        yield  # pragma: no cover

    monkeypatch.setattr(AgentLoop, "_iter_model_stream", always_fail)

    events = [
        event
        async for event in _make_loop().run_turn(_make_request(), turn_id="turn-retry-fail")
    ]

    assert call_count["n"] == 2
    error_events = [event for event in events if isinstance(event, ErrorEvent)]
    assert len(error_events) == 1
    assert error_events[0].code == "unexpected_model_behavior"


async def test_run_turn_content_filter_no_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_count = {"n": 0}

    async def content_filter_fail(
        self: AgentLoop, node: Any, ctx: Any, *, model_round: int = 0
    ) -> AsyncIterator[Any]:
        call_count["n"] += 1
        raise ContentFilterError("filtered")
        yield  # pragma: no cover

    monkeypatch.setattr(AgentLoop, "_iter_model_stream", content_filter_fail)

    events = [
        event
        async for event in _make_loop().run_turn(_make_request(), turn_id="turn-cf")
    ]

    assert call_count["n"] == 1
    error_events = [event for event in events if isinstance(event, ErrorEvent)]
    assert len(error_events) == 1
    assert error_events[0].code == "unexpected_model_behavior"


async def test_run_turn_read_tool_allows_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_model = AgentLoop._iter_model_stream
    model_calls = {"n": 0}
    tool_calls = {"n": 0}

    async def emit_read_then_model(
        self: AgentLoop,
        node: Any,
        ctx: Any,
        *,
        locale: str,
        work_id: str,
        hook_payload_base: dict[str, Any] | None = None,
        plugin_data_dir: Any = None,
    ) -> AsyncIterator[Any]:
        _ = locale, work_id, hook_payload_base, plugin_data_dir
        tool_calls["n"] += 1
        yield ToolCallResultEvent(
            tool_call_id="tc-read",
            tool_name="read_document",
            result={"content": "ok"},
            is_error=False,
        )

    async def fail_then_succeed(
        self: AgentLoop, node: Any, ctx: Any, *, model_round: int = 0
    ) -> AsyncIterator[Any]:
        model_calls["n"] += 1
        if model_calls["n"] == 1:
            raise UnexpectedModelBehavior("bad response")
        async for event in original_model(self, node, ctx, model_round=model_round):
            yield event

    monkeypatch.setattr(AgentLoop, "_iter_tool_stream", emit_read_then_model)
    monkeypatch.setattr(AgentLoop, "_iter_model_stream", fail_then_succeed)

    events = [
        event
        async for event in _make_loop().run_turn(_make_request(), turn_id="turn-read-retry")
    ]

    assert tool_calls["n"] >= 1
    assert model_calls["n"] >= 2
    assert any(isinstance(event, DoneEvent) for event in events)


async def test_run_turn_write_tool_blocks_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_calls = {"n": 0}

    async def emit_write_then_fail(
        self: AgentLoop,
        node: Any,
        ctx: Any,
        *,
        locale: str,
        work_id: str,
        hook_payload_base: dict[str, Any] | None = None,
        plugin_data_dir: Any = None,
    ) -> AsyncIterator[Any]:
        _ = node, ctx, locale, work_id, hook_payload_base, plugin_data_dir
        yield ToolCallResultEvent(
            tool_call_id="tc-write",
            tool_name="write_docx",
            result={"path": "out.docx"},
            is_error=False,
        )
        raise UnexpectedModelBehavior("bad response")
        yield  # pragma: no cover

    async def count_model_calls(
        self: AgentLoop, node: Any, ctx: Any, *, model_round: int = 0
    ) -> AsyncIterator[Any]:
        model_calls["n"] += 1
        if False:
            yield  # pragma: no cover

    monkeypatch.setattr(AgentLoop, "_iter_tool_stream", emit_write_then_fail)
    monkeypatch.setattr(AgentLoop, "_iter_model_stream", count_model_calls)

    events = [
        event
        async for event in _make_loop().run_turn(_make_request(), turn_id="turn-write-no-retry")
    ]

    assert model_calls["n"] <= 1
    error_events = [event for event in events if isinstance(event, ErrorEvent)]
    assert len(error_events) == 1
    assert error_events[0].code == "unexpected_model_behavior"


async def test_run_turn_emitted_preserved_after_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = AgentLoop._iter_model_stream
    call_count = {"n": 0}

    async def emit_token_then_fail_or_succeed(
        self: AgentLoop, node: Any, ctx: Any, *, model_round: int = 0
    ) -> AsyncIterator[Any]:
        call_count["n"] += 1
        if call_count["n"] == 1:
            yield TokenEvent(content="partial")
            raise UnexpectedModelBehavior("bad response")
        async for event in original(self, node, ctx, model_round=model_round):
            yield event

    monkeypatch.setattr(AgentLoop, "_iter_model_stream", emit_token_then_fail_or_succeed)

    events = [
        event
        async for event in _make_loop().run_turn(_make_request(), turn_id="turn-emitted")
    ]

    assert call_count["n"] >= 2
    assert any(isinstance(event, TokenEvent) for event in events)
    assert any(isinstance(event, DoneEvent) for event in events)
