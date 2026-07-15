"""Tests backend Tavily web_search."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.limits import DEFAULT_LIMITS
from app.schemas import ProviderSet, ProviderSetChat
from app.web_search.engine import search_web
from app.web_search.errors import WebSearchError
from app.web_search.tavily_backend import parse_tavily_response, search_tavily


TAVILY_RESPONSE = {
    "answer": "Paris weather is mild.",
    "results": [
        {
            "title": "Météo Paris",
            "url": "https://example.com/weather",
            "content": "Sunny in Paris today.",
            "source": "example.com",
        }
    ],
}


@pytest.mark.asyncio
async def test_search_tavily_posts_to_search_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    response = httpx.Response(
        200,
        json=TAVILY_RESPONSE,
        request=httpx.Request("POST", "https://api.tavily.com/search"),
    )
    post_mock = AsyncMock(return_value=response)

    with patch("app.web_search.tavily_backend.httpx.AsyncClient") as client_cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        client.post = post_mock
        client_cls.return_value = client

        payload = await search_tavily("weather Paris", api_key="tvly-test")

    assert payload["answer"] == "Paris weather is mild."
    post_mock.assert_awaited_once()
    call = post_mock.await_args
    assert call is not None
    assert call.args[0] == "https://api.tavily.com/search"
    body = call.kwargs["json"]
    assert body["query"] == "weather Paris"
    assert body["api_key"] == "tvly-test"


def test_parse_tavily_response_normalizes_results() -> None:
    parsed = parse_tavily_response(TAVILY_RESPONSE, max_results=8)
    assert len(parsed["results"]) == 1
    assert parsed["results"][0]["url"] == "https://example.com/weather"
    assert parsed["summary"] == "Paris weather is mild."


@pytest.mark.asyncio
async def test_search_web_ollama_uses_tavily_when_key_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.web_search.engine.resolve_tavily_api_key",
        lambda explicit_key=None: explicit_key or "tvly-test",
    )
    response = httpx.Response(
        200,
        json=TAVILY_RESPONSE,
        request=httpx.Request("POST", "https://api.tavily.com/search"),
    )
    post_mock = AsyncMock(return_value=response)

    with patch("app.web_search.tavily_backend.httpx.AsyncClient") as client_cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        client.post = post_mock
        client_cls.return_value = client

        result = await search_web(
            "Euro 2024 winner",
            provider_set=ProviderSet(
                id="ollama-test",
                chat=ProviderSetChat(provider="ollama", model="llama3.2"),
            ),
            locale="fr",
            limits=DEFAULT_LIMITS,
        )

    assert result["backend"] == "tavily"
    assert result["count"] == 1


@pytest.mark.asyncio
async def test_search_web_mistral_falls_back_to_tavily_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.web_search.engine.resolve_tavily_api_key",
        lambda explicit_key=None: explicit_key or "tvly-test",
    )
    tavily_response = httpx.Response(
        200,
        json=TAVILY_RESPONSE,
        request=httpx.Request("POST", "https://api.tavily.com/search"),
    )
    mistral_response = httpx.Response(
        503,
        json={"message": "unavailable"},
        request=httpx.Request("POST", "https://api.mistral.ai/v1/conversations"),
    )
    post_mock = AsyncMock(side_effect=[mistral_response, tavily_response])

    with patch("app.web_search.mistral_backend.httpx.AsyncClient") as mistral_client_cls, patch(
        "app.web_search.tavily_backend.httpx.AsyncClient"
    ) as tavily_client_cls:
        mistral_client = AsyncMock()
        mistral_client.__aenter__.return_value = mistral_client
        mistral_client.__aexit__.return_value = None
        mistral_client.post = post_mock
        mistral_client_cls.return_value = mistral_client

        tavily_client = AsyncMock()
        tavily_client.__aenter__.return_value = tavily_client
        tavily_client.__aexit__.return_value = None
        tavily_client.post = post_mock
        tavily_client_cls.return_value = tavily_client

        from pydantic import SecretStr

        result = await search_web(
            "weather Paris",
            provider_set=ProviderSet(
                id="mistral-test",
                chat=ProviderSetChat(
                    provider="mistral",
                    model="mistral-small-latest",
                    api_key=SecretStr("mistral-key"),
                    base_url="https://api.mistral.ai/v1",
                ),
            ),
            locale="fr",
            limits=DEFAULT_LIMITS,
        )

    assert result["backend"] == "tavily"
    assert result["count"] == 1


@pytest.mark.asyncio
async def test_search_tavily_maps_http_errors() -> None:
    response = httpx.Response(
        429,
        json={"error": "rate limit"},
        request=httpx.Request("POST", "https://api.tavily.com/search"),
    )
    post_mock = AsyncMock(return_value=response)

    with patch("app.web_search.tavily_backend.httpx.AsyncClient") as client_cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        client.post = post_mock
        client_cls.return_value = client

        with pytest.raises(WebSearchError) as exc:
            await search_tavily("weather", api_key="tvly-test")

    assert str(exc.value) == "web_search_rate_limit"
