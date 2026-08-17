"""Tests registre backends web search."""

from __future__ import annotations

from typing import Any

import pytest

from app.agent.tools import ToolContext
from app.limits import DEFAULT_LIMITS
from app.schemas import ProviderSet, ProviderSetChat
from app.web_search.backends import (
    clear_web_search_backends,
    register_web_search_backend,
    resolve_web_search_backend,
    run_registered_backend,
)
from app.web_search.engine import search_web
from app.web_search.errors import WebSearchError
from app.web_search.support import web_search_available


@pytest.fixture(autouse=True)
def _reset_backends() -> None:
    clear_web_search_backends()
    from app.web_search import engine as engine_module

    engine_module.register_web_search_backend("mistral", engine_module._mistral_registered_backend)
    engine_module.register_web_search_backend("ollama", engine_module._tavily_registered_backend)
    engine_module.register_web_search_backend("tavily", engine_module._tavily_registered_backend)
    engine_module.register_web_search_backend("cloud", engine_module._cloud_registered_backend)
    yield
    clear_web_search_backends()
    engine_module.register_web_search_backend("mistral", engine_module._mistral_registered_backend)
    engine_module.register_web_search_backend("ollama", engine_module._tavily_registered_backend)
    engine_module.register_web_search_backend("tavily", engine_module._tavily_registered_backend)
    engine_module.register_web_search_backend("cloud", engine_module._cloud_registered_backend)


@pytest.mark.asyncio
async def test_register_and_resolve_custom_backend() -> None:
    async def custom_backend(
        query: str,
        *,
        provider_set: Any = None,
        locale: str = "fr",
        limits: Any = None,
        premium: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        _ = (provider_set, locale, limits, premium)
        return {"outputs": []}

    register_web_search_backend("custom", custom_backend)
    assert resolve_web_search_backend("custom") is custom_backend

    payload = await run_registered_backend(
        "custom",
        "test query",
        provider_set=None,
        locale="fr",
        limits=DEFAULT_LIMITS,
    )
    assert payload == {"outputs": []}


@pytest.mark.asyncio
async def test_search_web_uses_unknown_provider_backend() -> None:
    async def custom_backend(
        query: str,
        *,
        provider_set: Any = None,
        locale: str = "fr",
        limits: Any = None,
        premium: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        _ = (provider_set, locale, limits, premium)
        return {
            "outputs": [
                {
                    "type": "message.output",
                    "content": [
                        {
                            "type": "tool_reference",
                            "title": "Example",
                            "url": "https://example.com",
                            "source": "web",
                        }
                    ],
                }
            ]
        }

    register_web_search_backend("openai", custom_backend)
    provider_set = ProviderSet(
        id="openai-test",
        chat=ProviderSetChat(provider="openai", model="gpt-test"),
    )
    result = await search_web(
        "cursor agents",
        provider_set=provider_set,
        locale="fr",
        limits=DEFAULT_LIMITS,
    )
    assert result["backend"] == "openai"
    assert result["count"] == 1


@pytest.mark.asyncio
async def test_search_web_accepts_finalized_registered_backend() -> None:
    async def custom_backend(
        query: str,
        *,
        provider_set: Any = None,
        locale: str = "fr",
        limits: Any = None,
        premium: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        _ = (provider_set, locale, limits, premium)
        return {
            "query": query,
            "count": 1,
            "backend": "custom",
            "results": [{"title": "T", "url": "https://x.test", "snippet": "s", "source": None}],
            "citations": [],
            "summary": "",
            "usage": {},
        }

    register_web_search_backend("openai", custom_backend)
    provider_set = ProviderSet(
        id="openai-test",
        chat=ProviderSetChat(provider="openai", model="gpt-test"),
    )
    result = await search_web(
        "test",
        provider_set=provider_set,
        locale="fr",
        limits=DEFAULT_LIMITS,
    )
    assert result["backend"] == "custom"
    assert result["count"] == 1


@pytest.mark.asyncio
async def test_search_web_unavailable_for_unregistered_provider() -> None:
    provider_set = ProviderSet(
        id="ollama-test",
        chat=ProviderSetChat(provider="ollama", model="llama3"),
    )
    with pytest.raises(WebSearchError):
        await search_web(
            "weather",
            provider_set=provider_set,
            locale="fr",
            limits=DEFAULT_LIMITS,
        )


def _tool_context_for_provider(provider: str, *, network: bool = True) -> ToolContext:
    return ToolContext(
        tenant_id="t",
        project_id="p",
        session_id="s",
        documents=[],
        provider_set=ProviderSet(
            id=f"{provider}-test",
            chat=ProviderSetChat(provider=provider, model="test-model"),
        ),
        permissions_network=network,
    )


def test_web_search_available_uses_registered_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.web_search.support.resolve_tavily_api_key",
        lambda explicit_key=None: None,
    )
    async def custom_backend(
        query: str,
        *,
        provider_set: Any = None,
        locale: str = "fr",
        limits: Any = None,
        premium: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        _ = (query, provider_set, locale, limits, premium)
        return {"outputs": []}

    register_web_search_backend("openai", custom_backend)

    assert web_search_available(_tool_context_for_provider("openai")) is True
    assert web_search_available(_tool_context_for_provider("ollama")) is False
    assert web_search_available(_tool_context_for_provider("openai", network=False)) is False


def test_web_search_available_mistral_by_default() -> None:
    assert web_search_available(_tool_context_for_provider("mistral")) is True


def test_web_search_available_cloud_requires_enrollment(tmp_path) -> None:
    from pathlib import Path

    cloud_dir = tmp_path / "workproba.cloud"
    cloud_dir.mkdir()
    context = ToolContext(
        tenant_id="t",
        project_id="p",
        session_id="s",
        documents=[],
        cloud_plugin_data_dir=cloud_dir,
        provider_set=ProviderSet(
            id="workproba-cloud",
            auth_mode="device_bearer",
            chat=ProviderSetChat(provider="mistral", model="mistral-medium-latest"),
        ),
        permissions_network=True,
    )
    assert web_search_available(context) is False

    (cloud_dir / "config.json").write_text(
        '{"base_url": "https://cloud.example.test", "tokens": {"access_token": "wp_dev_x"}}',
        encoding="utf-8",
    )
    assert web_search_available(context) is True

    locked = ToolContext(
        tenant_id="t",
        project_id="p",
        session_id="s",
        documents=[],
        cloud_plugin_data_dir=cloud_dir,
        provider_set=ProviderSet(
            id="workproba-cloud",
            auth_mode="device_bearer",
            chat=ProviderSetChat(provider="mistral", model="mistral-medium-latest"),
        ),
        permissions_network=False,
    )
    assert web_search_available(locked) is False


def test_web_search_available_cloud_from_plugins_root(tmp_path) -> None:
    import json

    plugins = tmp_path / "plugins"
    cloud_dir = plugins / "workproba.cloud"
    cloud_dir.mkdir(parents=True)
    (cloud_dir / "config.json").write_text(
        json.dumps(
            {
                "base_url": "https://cloud.example.test",
                "tokens": {"access_token": "wp_dev_x"},
            }
        ),
        encoding="utf-8",
    )
    context = ToolContext(
        tenant_id="t",
        project_id="p",
        session_id="s",
        documents=[],
        plugin_data_dir=plugins,
        provider_set=ProviderSet(
            id="workproba-cloud",
            auth_mode="device_bearer",
            chat=ProviderSetChat(provider="mistral", model="mistral-medium-latest"),
        ),
        permissions_network=True,
    )
    assert web_search_available(context) is True
