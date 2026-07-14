"""Tests registre backends web search."""

from __future__ import annotations

from typing import Any

import pytest

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


@pytest.fixture(autouse=True)
def _reset_backends() -> None:
    clear_web_search_backends()
    from app.web_search import engine as engine_module

    engine_module.register_web_search_backend("mistral", engine_module._mistral_registered_backend)
    yield
    clear_web_search_backends()
    engine_module.register_web_search_backend("mistral", engine_module._mistral_registered_backend)


@pytest.mark.asyncio
async def test_register_and_resolve_custom_backend() -> None:
    async def custom_backend(
        query: str,
        *,
        provider_set: Any = None,
        locale: str = "fr",
        limits: Any = None,
        premium: bool = False,
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
