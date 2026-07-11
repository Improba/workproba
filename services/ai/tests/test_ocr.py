"""Tests OCR Mistral (mock HTTP)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from pydantic import SecretStr

from app.llm.provider_sets import MISTRAL_BUILTIN_SET
from app.ocr.mistral import MistralOcrClient, _parse_ocr_response
from app.schemas import ProviderSetOcr


def test_parse_ocr_response_markdown_pages() -> None:
    data = {
        "model": "mistral-ocr-latest",
        "pages": [
            {"index": 0, "markdown": "Page un"},
            {"index": 1, "markdown": "Page deux"},
        ],
    }
    result = _parse_ocr_response(data)
    assert "Page un" in result.text
    assert "Page deux" in result.text
    assert result.pages_processed == 2


@pytest.mark.asyncio
async def test_mistral_ocr_client_posts_base64_document() -> None:
    provider_set = MISTRAL_BUILTIN_SET.model_copy(
        update={
            "chat": MISTRAL_BUILTIN_SET.chat.model_copy(
                update={"api_key": SecretStr("secret")}
            )
        }
    )
    client = MistralOcrClient(provider_set=provider_set)

    response = httpx.Response(
        200,
        json={
            "pages": [{"markdown": "Bonjour"}],
            "model": "mistral-ocr-latest",
        },
        request=httpx.Request("POST", "https://api.mistral.ai/v1/ocr"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post_mock:
        post_mock.return_value = response
        result = await client.ocr_pdf(b"%PDF-test", max_pages=2)

    assert result.text == "Bonjour"
    post_mock.assert_awaited_once()
    call_kwargs = post_mock.await_args.kwargs
    payload = call_kwargs["json"]
    assert payload["model"] == "mistral-ocr-latest"
    assert payload["document"]["type"] == "document_url"
    assert payload["document"]["document_url"].startswith("data:application/pdf;base64,")
    assert payload["pages"] == "0,1"


def test_mistral_ocr_uses_ocr_block_api_key() -> None:
    provider_set = MISTRAL_BUILTIN_SET.model_copy(
        update={
            "chat": MISTRAL_BUILTIN_SET.chat.model_copy(
                update={"api_key": SecretStr("chat-key")}
            ),
            "ocr": ProviderSetOcr(
                provider="mistral",
                mode="auto",
                api_key=SecretStr("ocr-key"),
            ),
        }
    )
    client = MistralOcrClient(provider_set=provider_set)
    assert client._api_key == "ocr-key"
