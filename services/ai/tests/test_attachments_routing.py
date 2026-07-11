"""Tests routage pièces jointes par capacités ProviderSet."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, patch

from pydantic import SecretStr

from app.agent.attachments import process_inline_attachments
from app.limits import DEFAULT_LIMITS
from app.llm.provider_sets import MISTRAL_BUILTIN_SET
from app.ocr.mistral import OcrResult
from app.schemas import (
    ProviderSet,
    ProviderSetCapabilities,
    ProviderSetChat,
    ProviderSetOcr,
    ProviderSetVision,
)
from app.schemas import DocumentReference


def _doc(
    name: str,
    content: bytes,
    *,
    mime_type: str | None = None,
    doc_id: str | None = None,
) -> DocumentReference:
    return DocumentReference(
        id=doc_id or name,
        name=name,
        mime_type=mime_type,
        content_base64=base64.b64encode(content).decode("ascii"),
        size_bytes=len(content),
    )


def _vision_set() -> ProviderSet:
    return MISTRAL_BUILTIN_SET.model_copy(
        update={
            "chat": MISTRAL_BUILTIN_SET.chat.model_copy(
                update={"api_key": SecretStr("test-key")}
            )
        }
    )


def _ocr_set() -> ProviderSet:
    return _vision_set().model_copy(
        update={
            "capabilities": ProviderSetCapabilities(
                reasoning="medium", vision=False, tools=True
            ),
            "vision": ProviderSetVision(mode="none"),
            "ocr": ProviderSetOcr(provider="mistral", mode="auto"),
        }
    )


async def test_image_with_vision_injects_binary_part() -> None:
    d = _doc("photo.png", b"\x89PNG\x00", mime_type="image/png")
    result = await process_inline_attachments(
        [d], DEFAULT_LIMITS, provider_set=_vision_set()
    )
    assert len(result.vision_parts) == 1
    assert result.statuses[0].status_key == "viewed"
    assert "vision" in result.context_text.lower()


async def test_image_without_vision_is_unavailable() -> None:
    d = _doc("photo.png", b"\x89PNG\x00", mime_type="image/png")
    result = await process_inline_attachments(
        [d],
        DEFAULT_LIMITS,
        provider_set=ProviderSet(
            id="minimal",
            name="Minimal",
            chat=ProviderSetChat(provider="mistral", model="mistral-small-latest"),
            capabilities=ProviderSetCapabilities(vision=False),
            vision=ProviderSetVision(mode="none"),
        ),
    )
    assert result.vision_parts == []
    assert result.statuses[0].status_key == "unavailable"
    assert "Lecture non disponible" in result.statuses[0].label_locale


async def test_image_locked_mode_no_switch_hint() -> None:
    d = _doc("photo.png", b"\x89PNG\x00", mime_type="image/png")
    result = await process_inline_attachments(
        [d],
        DEFAULT_LIMITS,
        provider_set=ProviderSet(
            id="minimal",
            name="Minimal",
            chat=ProviderSetChat(provider="mistral", model="mistral-small-latest"),
            capabilities=ProviderSetCapabilities(vision=False),
            vision=ProviderSetVision(mode="none"),
        ),
        ui_mode="locked",
    )
    assert "moteur imposé" in result.context_text


async def test_docx_status_word() -> None:
    from docx import Document
    from io import BytesIO

    buf = BytesIO()
    doc = Document()
    doc.add_paragraph("Hello")
    doc.save(buf)
    d = _doc("note.docx", buf.getvalue())
    result = await process_inline_attachments(
        [d], DEFAULT_LIMITS, provider_set=_vision_set()
    )
    assert result.statuses[0].status_key == "word"
    assert "Hello" in result.context_text


async def test_scanned_pdf_ocr_route() -> None:
    d = _doc("scan.pdf", b"%PDF-fake", mime_type="application/pdf")
    ocr_result = OcrResult(text="Texte OCR", pages_processed=1, metadata={})

    with (
        patch("app.agent.attachments.is_scanned_pdf", return_value=True),
        patch(
            "app.agent.attachments.MistralOcrClient.ocr_pdf",
            new_callable=AsyncMock,
            return_value=ocr_result,
        ),
    ):
        result = await process_inline_attachments(
            [d], DEFAULT_LIMITS, provider_set=_ocr_set()
        )

    assert result.statuses[0].status_key == "scanned_pdf"
    assert "Texte OCR" in result.context_text


async def test_scanned_pdf_vision_fallback() -> None:
    d = _doc("scan.pdf", b"%PDF-fake", mime_type="application/pdf")
    vision_only = _vision_set().model_copy(
        update={"ocr": ProviderSetOcr(provider="mistral", mode="none")}
    )

    with (
        patch("app.agent.attachments.is_scanned_pdf", return_value=True),
        patch(
            "app.agent.attachments._pdf_pages_to_images",
            return_value=[],
        ),
    ):
        result = await process_inline_attachments(
            [d], DEFAULT_LIMITS, provider_set=vision_only
        )

    assert result.statuses[0].status_key == "unavailable"
