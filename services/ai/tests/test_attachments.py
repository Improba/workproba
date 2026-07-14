"""Tests de l'injection des pièces jointes inline dans le contexte du tour."""

from __future__ import annotations

import base64

from app.agent.attachments import build_inline_attachments_context
from app.limits import DEFAULT_LIMITS
from app.schemas import DocumentReference


def _doc(
    name: str, content: bytes, *, mime_type: str | None = None, kind: str | None = None
) -> DocumentReference:
    return DocumentReference(
        id=name,
        name=name,
        mime_type=mime_type,
        content_base64=base64.b64encode(content).decode("ascii"),
        kind=kind,
        size_bytes=len(content),
    )


async def test_no_inline_documents_returns_empty() -> None:
    out = await build_inline_attachments_context([], DEFAULT_LIMITS)
    assert out == ""


async def test_project_documents_without_content_base64_are_ignored() -> None:
    d = DocumentReference(id="proj/a.txt", name="a.txt", mime_type="text/plain")
    out = await build_inline_attachments_context([d], DEFAULT_LIMITS)
    assert out == ""


async def test_text_attachment_is_inlined() -> None:
    d = _doc("note.txt", b"hello world", mime_type="text/plain", kind="text")
    out = await build_inline_attachments_context([d], DEFAULT_LIMITS)
    assert "Pièce jointe : note.txt" in out
    assert "hello world" in out
    assert "<untrusted>" in out


async def test_image_attachment_is_placeholder() -> None:
    d = _doc("photo.png", b"\x89PNG fake", mime_type="image/png", kind="image")
    out = await build_inline_attachments_context([d], DEFAULT_LIMITS)
    assert "Pièce jointe (image) : photo.png" in out
    assert "fake" not in out  # les bytes ne fuient pas dans le contexte


async def test_invalid_base64_is_reported_not_fatal() -> None:
    d = DocumentReference(
        id="bad",
        name="bad.bin",
        mime_type="application/octet-stream",
        content_base64="!!not base64!!",
        kind="document",
        size_bytes=0,
    )
    out = await build_inline_attachments_context([d], DEFAULT_LIMITS)
    assert "contenu illisible" in out


async def test_text_is_truncated_above_limit() -> None:
    big = "A" * (DEFAULT_LIMITS.extract_max_chars + 50)
    d = _doc("big.txt", big.encode("utf-8"), mime_type="text/plain", kind="text")
    out = await build_inline_attachments_context([d], DEFAULT_LIMITS)
    assert "tronqué" in out
    assert big not in out
