"""Tests outil core web_search."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel

from app.agent.human import build_human_summary
from app.agent.tools import ToolDeps, ToolContext, build_agent
from app.limits import DEFAULT_LIMITS, Limits
from app.schemas import ProviderSet, ProviderSetChat
from app.sandbox.runner import SandboxRunner
from app.web_search import engine as web_search_engine
from app.web_search import set_search_backend
from conftest import FakeProjectClient
from fixtures.mistral_web_search_response import MISTRAL_WEB_SEARCH_RESPONSE


def _mistral_provider_set() -> ProviderSet:
    return ProviderSet(
        id="mistral-test",
        chat=ProviderSetChat(
            provider="mistral",
            model="mistral-small-latest",
            api_key=SecretStr("test-key"),
            base_url="https://api.mistral.ai/v1",
        ),
    )


async def _mock_search_backend(
    query: str,
    *,
    provider_set: Any = None,
    locale: str = "fr",
    limits: Limits | None = None,
    premium: bool = False,
) -> dict[str, Any]:
    _ = (provider_set, locale, limits, premium)
    parsed = web_search_engine.parse_mistral_conversation_response(
        MISTRAL_WEB_SEARCH_RESPONSE,
        max_results=8,
    )
    return web_search_engine._finalize(query, parsed, backend="mock")  # noqa: SLF001


@pytest.fixture(autouse=True)
def _mock_web_search_backend() -> None:
    set_search_backend(_mock_search_backend)
    yield
    set_search_backend(None)


@pytest.fixture
def plugin_dir(tmp_path: Path) -> Path:
    path = tmp_path / "plugins" / "workproba.web_search"
    path.mkdir(parents=True)
    return path


def test_web_search_tool_always_registered() -> None:
    agent = build_agent(TestModel())
    assert "web_search" in agent._function_toolset.tools


@pytest.mark.asyncio
async def test_web_search_tool_returns_results(plugin_dir: Path) -> None:
    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s1",
            documents=[],
            plugin_data_dir=plugin_dir,
            locale="fr",
            permissions_network=True,
            provider_set=_mistral_provider_set(),
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
    )
    agent = build_agent(TestModel())
    tool = agent._function_toolset.tools["web_search"]
    ctx = RunContext(deps=deps, model=TestModel(), usage=None, prompt=None, tool_call_id="tc1")
    result = await tool.function(ctx, query="Euro 2024 winner")
    assert result["query"] == "Euro 2024 winner"
    assert result["count"] == 2
    assert result["backend"] == "mock"
    assert result["results"][0]["url"].startswith("https://")
    assert deps.web_search_calls == 1


@pytest.mark.asyncio
async def test_web_search_tool_blocked_in_locked_mode(plugin_dir: Path) -> None:
    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s1",
            documents=[],
            plugin_data_dir=plugin_dir,
            locale="fr",
            settings_locked=True,
            permissions_network=False,
            provider_set=_mistral_provider_set(),
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
    )
    agent = build_agent(TestModel())
    tool = agent._function_toolset.tools["web_search"]
    ctx = RunContext(deps=deps, model=TestModel(), usage=None, prompt=None, tool_call_id="tc1")
    with pytest.raises(Exception) as exc:
        await tool.function(ctx, query="weather Paris")
    message = str(exc.value).lower()
    assert (
        "verrouillé" in message
        or "locked" in message
        or "bloqué" in message
        or "interdite" in message
    )


@pytest.mark.asyncio
async def test_web_search_unavailable_without_mistral(plugin_dir: Path) -> None:
    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s1",
            documents=[],
            plugin_data_dir=plugin_dir,
            locale="en",
            permissions_network=True,
            provider_set=ProviderSet(
                id="ollama-test",
                chat=ProviderSetChat(provider="ollama", model="llama3"),
            ),
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
    )
    agent = build_agent(TestModel())
    tool = agent._function_toolset.tools["web_search"]
    ctx = RunContext(deps=deps, model=TestModel(), usage=None, prompt=None, tool_call_id="tc1")
    with pytest.raises(Exception) as exc:
        await tool.function(ctx, query="weather Paris")
    message = str(exc.value).lower()
    assert "unavailable" in message or "indisponible" in message


@pytest.mark.asyncio
async def test_web_search_respects_max_per_turn(plugin_dir: Path) -> None:
    limits = Limits(web_search_max_per_turn=1)
    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s1",
            documents=[],
            plugin_data_dir=plugin_dir,
            locale="en",
            permissions_network=True,
            provider_set=_mistral_provider_set(),
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=limits,
    )
    agent = build_agent(TestModel())
    tool = agent._function_toolset.tools["web_search"]
    ctx = RunContext(deps=deps, model=TestModel(), usage=None, prompt=None, tool_call_id="tc1")
    await tool.function(ctx, query="first")
    with pytest.raises(Exception) as exc:
        await tool.function(ctx, query="second")
    assert "limit" in str(exc.value).lower()


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_human_summary_web_search(locale: str) -> None:
    will = build_human_summary("web_search", {"query": "météo Paris"}, locale=locale)
    if locale == "fr":
        assert "Je cherche sur le web" in will
        assert "météo Paris" in will
    else:
        assert "Searching the web" in will

    done = build_human_summary(
        "web_search",
        {"query": "météo Paris"},
        result={"results": [{"url": "https://x.test"}]},
        locale=locale,
    )
    if locale == "fr":
        assert "1 résultat web" in done
    else:
        assert "1 web result" in done
