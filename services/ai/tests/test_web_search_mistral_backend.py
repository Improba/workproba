"""Tests HTTP backend Mistral web_search."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.web_search.errors import WebSearchError
from app.web_search.mistral_backend import search_mistral
from fixtures.mistral_web_search_response import MISTRAL_WEB_SEARCH_RESPONSE


@pytest.mark.asyncio
async def test_search_mistral_posts_to_conversations_endpoint() -> None:
    response = httpx.Response(
        200,
        json=MISTRAL_WEB_SEARCH_RESPONSE,
        request=httpx.Request("POST", "https://api.mistral.ai/v1/conversations"),
    )
    post_mock = AsyncMock(return_value=response)

    with patch("app.web_search.mistral_backend.httpx.AsyncClient") as client_cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        client.post = post_mock
        client_cls.return_value = client

        result = await search_mistral(
            "Euro 2024 winner",
            model="mistral-small-latest",
            api_key="test-key",
            base_url="https://api.mistral.ai/v1",
        )

    assert result["object"] == "conversation.response"
    post_mock.assert_awaited_once()
    call = post_mock.await_args
    assert call is not None
    assert call.args[0] == "https://api.mistral.ai/v1/conversations"
    payload = call.kwargs["json"]
    assert payload["model"] == "mistral-small-latest"
    assert payload["tools"] == [{"type": "web_search"}]
    assert payload["inputs"] == "Euro 2024 winner"
    assert payload["stream"] is False
    headers = call.kwargs["headers"]
    assert headers["Authorization"] == "Bearer test-key"


@pytest.mark.asyncio
async def test_search_mistral_maps_http_errors() -> None:
    response = httpx.Response(
        429,
        json={"message": "rate limit"},
        request=httpx.Request("POST", "https://api.mistral.ai/v1/conversations"),
    )
    post_mock = AsyncMock(return_value=response)

    with patch("app.web_search.mistral_backend.httpx.AsyncClient") as client_cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        client.post = post_mock
        client_cls.return_value = client

        with pytest.raises(WebSearchError) as exc:
            await search_mistral(
                "weather",
                model="mistral-small-latest",
                api_key="test-key",
                base_url="https://api.mistral.ai/v1",
            )

    assert str(exc.value) == "web_search_rate_limit"
