"""Client OCR Mistral (POST /v1/ocr)."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

import httpx

from app.schemas import ProviderSet


@dataclass(frozen=True)
class OcrResult:
    text: str
    pages_processed: int
    metadata: dict[str, Any]


def resolve_ocr_api_key(provider_set: ProviderSet) -> str:
    """Résout la clé OCR : bloc ocr puis repli sur chat."""
    ocr = provider_set.ocr
    if ocr is not None and ocr.api_key is not None:
        return ocr.api_key.get_secret_value()
    chat = provider_set.chat
    if chat is not None and chat.api_key is not None:
        return chat.api_key.get_secret_value()
    return ""


def resolve_ocr_base_url(provider_set: ProviderSet) -> str:
    ocr = provider_set.ocr
    if ocr is not None and ocr.base_url:
        return ocr.base_url.rstrip("/")
    chat = provider_set.chat
    if chat is not None and chat.base_url:
        return chat.base_url.rstrip("/")
    return "https://api.mistral.ai/v1"


class MistralOcrClient:
    def __init__(
        self,
        *,
        provider_set: ProviderSet,
        timeout_seconds: float = 120.0,
    ) -> None:
        ocr = provider_set.ocr
        if ocr is None or ocr.provider != "mistral":
            raise ValueError("Mistral OCR config missing from provider set")
        self._base_url = resolve_ocr_base_url(provider_set)
        self._api_key = resolve_ocr_api_key(provider_set)
        self._model = ocr.model or "mistral-ocr-latest"
        self._timeout = timeout_seconds

    async def ocr_pdf(
        self,
        content: bytes,
        *,
        mime_type: str = "application/pdf",
        max_pages: int = 30,
    ) -> OcrResult:
        if not self._api_key:
            raise ValueError("OCR API key missing from provider set chat config")

        data_url = (
            f"data:{mime_type};base64,"
            f"{base64.b64encode(content).decode('ascii')}"
        )
        pages_spec: str | None = None
        if max_pages > 0:
            pages_spec = ",".join(str(index) for index in range(max_pages))

        payload: dict[str, Any] = {
            "model": self._model,
            "document": {
                "type": "document_url",
                "document_url": data_url,
            },
        }
        if pages_spec:
            payload["pages"] = pages_spec

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/ocr",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        return _parse_ocr_response(data)


def _parse_ocr_response(data: dict[str, Any]) -> OcrResult:
    pages = data.get("pages")
    chunks: list[str] = []
    pages_processed = 0
    if isinstance(pages, list):
        pages_processed = len(pages)
        for page in pages:
            if not isinstance(page, dict):
                continue
            markdown = page.get("markdown")
            if isinstance(markdown, str) and markdown.strip():
                chunks.append(markdown.strip())
                continue
            text = page.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())

    text = "\n\n".join(chunks).strip()
    usage = data.get("usage_info") if isinstance(data.get("usage_info"), dict) else {}
    return OcrResult(
        text=text,
        pages_processed=pages_processed,
        metadata={
            "model": data.get("model"),
            "pages_processed": pages_processed,
            "usage_info": usage,
        },
    )
