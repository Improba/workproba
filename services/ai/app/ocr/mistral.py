"""Client OCR Mistral (POST /v1/ocr)."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.llm.provider_sets import (
    CloudNotEnrolledError,
    build_cloud_llm_base_url,
    resolve_cloud_plugin_data_dir,
)
from app.plugins.workproba_cloud.storage import (
    get_access_token,
    get_control_plane_base_url,
)
from app.schemas import ProviderSet


@dataclass(frozen=True)
class OcrResult:
    text: str
    pages_processed: int
    metadata: dict[str, Any]


def resolve_ocr_api_key(
    provider_set: ProviderSet,
    *,
    cloud_plugin_data_dir: Path | str | None = None,
    plugin_data_dir: Path | str | None = None,
) -> str:
    """Résout la clé OCR : bloc ocr puis repli sur chat ou DeviceBearer cloud."""
    if provider_set.auth_mode == "device_bearer":
        cloud_dir = resolve_cloud_plugin_data_dir(
            cloud_plugin_data_dir=cloud_plugin_data_dir,
            plugin_data_dir=plugin_data_dir,
        )
        if cloud_dir is None:
            raise CloudNotEnrolledError()
        token = get_access_token(cloud_dir)
        if not token:
            raise CloudNotEnrolledError()
        return token
    ocr = provider_set.ocr
    if ocr is not None and ocr.api_key is not None:
        return ocr.api_key.get_secret_value()
    chat = provider_set.chat
    if chat is not None and chat.api_key is not None:
        return chat.api_key.get_secret_value()
    return ""


def resolve_ocr_base_url(
    provider_set: ProviderSet,
    *,
    cloud_plugin_data_dir: Path | str | None = None,
    plugin_data_dir: Path | str | None = None,
) -> str:
    if provider_set.auth_mode == "device_bearer":
        # Pas de repli Mistral public : le token device ne doit jamais
        # être envoyé hors du plan de contrôle.
        cloud_dir = resolve_cloud_plugin_data_dir(
            cloud_plugin_data_dir=cloud_plugin_data_dir,
            plugin_data_dir=plugin_data_dir,
        )
        if cloud_dir is None:
            raise CloudNotEnrolledError()
        control_plane = get_control_plane_base_url(cloud_dir)
        if not control_plane:
            raise CloudNotEnrolledError()
        return build_cloud_llm_base_url(control_plane)
    ocr = provider_set.ocr
    if ocr is not None and ocr.base_url:
        return ocr.base_url.rstrip("/")
    chat = provider_set.chat
    if chat is not None and chat.base_url:
        return chat.base_url.rstrip("/")
    return "https://api.mistral.ai/v1"


CLOUD_OCR_TIMEOUT_SECONDS = 180.0


class MistralOcrClient:
    def __init__(
        self,
        *,
        provider_set: ProviderSet,
        timeout_seconds: float | None = None,
        cloud_plugin_data_dir: Path | str | None = None,
        plugin_data_dir: Path | str | None = None,
    ) -> None:
        ocr = provider_set.ocr
        if ocr is None or ocr.provider != "mistral":
            raise ValueError("Mistral OCR config missing from provider set")
        self._base_url = resolve_ocr_base_url(
            provider_set,
            cloud_plugin_data_dir=cloud_plugin_data_dir,
            plugin_data_dir=plugin_data_dir,
        )
        self._api_key = resolve_ocr_api_key(
            provider_set,
            cloud_plugin_data_dir=cloud_plugin_data_dir,
            plugin_data_dir=plugin_data_dir,
        )
        self._model = ocr.model or "mistral-ocr-latest"
        if timeout_seconds is not None:
            self._timeout = timeout_seconds
        elif provider_set.auth_mode == "device_bearer":
            self._timeout = CLOUD_OCR_TIMEOUT_SECONDS
        else:
            self._timeout = 120.0

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
