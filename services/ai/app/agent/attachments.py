"""Injection des pièces jointes au message utilisateur dans le contexte du tour.

Routage par capacités du ProviderSet actif (vision, OCR) avec statuts honnêtes.
Sans provider set : comportement V1 (extraction texte native, placeholder images).
"""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

from pydantic_ai.messages import BinaryContent

from app.documents.extractor import LocalExtractor, is_binary_document
from app.i18n import DEFAULT_LOCALE, attachment_status_label, t
from app.limits import Limits
from app.llm.provider_sets import CloudNotEnrolledError
from app.ocr import MistralOcrClient, is_scanned_pdf
from app.provider_set import (
    ProviderSet,
    is_locked_mode,
    ocr_available,
    vision_available,
)
from app.schemas import DocumentReference


_IMAGE_MIMES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/gif",
}

_TEXT_MIMES = {
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/json",
}

_TEXT_EXTS = {".txt", ".md", ".csv", ".json"}

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class ReprocessAttachmentResult:
    status_key: str
    label_locale: str
    extracted_text: str | None = None


def attachment_relative_path(
    session_id: str,
    attachment_id: str,
    file_name: str,
) -> str:
    """Chemin relatif sous workspace_data_dir pour une pièce jointe chat."""
    safe_name = _SAFE_FILENAME_RE.sub("_", file_name.strip()) or "attachment"
    return f"attachments/{session_id}/{attachment_id}/{safe_name}"


def _resolve_attachment_path(
    workspace_data_dir: Path,
    file_path: str,
) -> Path:
    workspace_root = workspace_data_dir.expanduser().resolve()
    normalized = file_path.replace("\\", "/").lstrip("/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    target = (workspace_root / normalized).resolve()
    if not target.is_relative_to(workspace_root):
        raise ValueError("Path outside workspace")
    return target


def persist_attachment_file(
    workspace_data_dir: Path,
    *,
    session_id: str,
    attachment_id: str,
    file_name: str,
    content: bytes,
    file_path: str | None = None,
) -> str:
    """Copie la pièce brute dans workspace_data_dir et renvoie le chemin relatif."""
    relative = file_path or attachment_relative_path(
        session_id,
        attachment_id,
        file_name,
    )
    target = _resolve_attachment_path(workspace_data_dir, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return relative


async def reprocess_attachment(
    *,
    workspace_data_dir: Path,
    attachment_id: str,
    file_path: str,
    file_name: str,
    mime_type: str | None,
    limits: Limits,
    locale: str = DEFAULT_LOCALE,
    provider_set: ProviderSet | None = None,
    ui_mode: str = "guided",
    cloud_plugin_data_dir: Path | None = None,
    plugin_data_dir: Path | None = None,
) -> ReprocessAttachmentResult:
    """Re-traite une pièce stockée avec le set fourni (sans tour agent)."""
    target = _resolve_attachment_path(workspace_data_dir, file_path)
    if not target.is_file():
        raise FileNotFoundError(f"Attachment file not found: {file_path}")
    content = target.read_bytes()
    doc = DocumentReference(
        id=attachment_id,
        name=file_name,
        mime_type=mime_type,
        content_base64=base64.b64encode(content).decode("ascii"),
        size_bytes=len(content),
    )
    processed = await process_inline_attachments(
        [doc],
        limits,
        locale=locale,
        provider_set=provider_set,
        ui_mode=ui_mode,
        cloud_plugin_data_dir=cloud_plugin_data_dir,
        plugin_data_dir=plugin_data_dir,
    )
    if not processed.statuses:
        return ReprocessAttachmentResult(
            status_key="unavailable",
            label_locale=attachment_status_label(locale, "unavailable"),
        )
    status = processed.statuses[0]
    extracted_text: str | None = None
    if processed.context_text:
        extracted_text = processed.context_text
    return ReprocessAttachmentResult(
        status_key=status.status_key,
        label_locale=status.label_locale,
        extracted_text=extracted_text,
    )


@dataclass(frozen=True)
class AttachmentStatusInfo:
    attachment_id: str
    status_key: str
    label_locale: str


@dataclass
class ProcessedAttachments:
    context_text: str = ""
    vision_parts: list[BinaryContent] = field(default_factory=list)
    statuses: list[AttachmentStatusInfo] = field(default_factory=list)


def _ext(name: str) -> str:
    dot = name.rfind(".")
    return name[dot:].lower() if dot >= 0 else ""


def _is_text(name: str, mime_type: str | None) -> bool:
    if mime_type and mime_type in _TEXT_MIMES:
        return True
    if mime_type and mime_type.startswith("text/"):
        return True
    return _ext(name) in _TEXT_EXTS


def _is_image(name: str, mime_type: str | None) -> bool:
    if mime_type and mime_type in _IMAGE_MIMES:
        return True
    return _ext(name) in {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _is_docx(name: str, mime_type: str | None) -> bool:
    return _ext(name) == ".docx" or mime_type == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


def _is_xlsx(name: str, mime_type: str | None) -> bool:
    return _ext(name) == ".xlsx" or mime_type == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def _is_pdf(name: str, mime_type: str | None) -> bool:
    return _ext(name) == ".pdf" or mime_type == "application/pdf"


def _image_media_type(mime_type: str | None, name: str) -> str:
    if mime_type in _IMAGE_MIMES:
        return "image/jpeg" if mime_type == "image/jpg" else mime_type
    ext = _ext(name)
    mapping = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    return mapping.get(ext, "image/png")


def _format_size(size_bytes: int | None, locale: str) -> str:
    if not size_bytes:
        return t(locale, "attachments.size_unknown")
    if size_bytes < 1024:
        return t(locale, "attachments.size_bytes", size=size_bytes)
    if size_bytes < 1024 * 1024:
        return t(locale, "attachments.size_kb", size=size_bytes // 1024)
    return t(locale, "attachments.size_mb", size=f"{size_bytes / (1024 * 1024):.1f}")


def _decode_base64(content_base64: str) -> bytes | None:
    try:
        return base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError):
        return None


def _wrap_untrusted_document_content(text: str, locale: str) -> str:
    from app.agent.untrusted import wrap_untrusted_content

    return wrap_untrusted_content(text, locale, "attachments.untrusted_header")


def _format_extracted_document_block(
    doc: DocumentReference,
    text: str,
    locale: str,
    *,
    note: str = "",
) -> str:
    wrapped = _wrap_untrusted_document_content(text, locale)
    return (
        f"### {t(locale, 'attachments.title', name=doc.name)}\n"
        f"```\n{wrapped}\n```{note}"
    )


def _status(
    doc_id: str,
    status_key: str,
    locale: str,
) -> AttachmentStatusInfo:
    return AttachmentStatusInfo(
        attachment_id=doc_id,
        status_key=status_key,
        label_locale=attachment_status_label(locale, status_key),
    )


def _unavailable_block(
    doc: DocumentReference,
    locale: str,
    *,
    locked: bool,
) -> str:
    if locked:
        return t(locale, "attachments.unavailable_locked", name=doc.name)
    return t(locale, "attachments.unavailable_guided", name=doc.name)


def _pdf_pages_to_images(
    content: bytes,
    *,
    max_pages: int,
) -> list[BinaryContent]:
    import pdfplumber

    parts: list[BinaryContent] = []
    with pdfplumber.open(BytesIO(content)) as pdf:
        for page in pdf.pages[:max_pages]:
            try:
                image = page.to_image(resolution=150).original
                buf = BytesIO()
                image.save(buf, format="PNG")
                parts.append(
                    BinaryContent(data=buf.getvalue(), media_type="image/png")
                )
            except Exception:
                continue
    return parts


async def process_inline_attachments(
    documents: list[DocumentReference],
    limits: Limits,
    *,
    locale: str = DEFAULT_LOCALE,
    provider_set: ProviderSet | None = None,
    ui_mode: str = "guided",
    cloud_plugin_data_dir: Path | None = None,
    plugin_data_dir: Path | None = None,
) -> ProcessedAttachments:
    """Route et traite les pièces jointes inline selon les capacités du set."""
    inline = [d for d in documents if d.content_base64]
    if not inline:
        return ProcessedAttachments()

    extractor = LocalExtractor(limits=limits)
    blocks: list[str] = []
    vision_parts: list[BinaryContent] = []
    statuses: list[AttachmentStatusInfo] = []

    has_vision = vision_available(provider_set)
    has_ocr = ocr_available(provider_set)
    locked = is_locked_mode(provider_set, ui_mode)
    ocr_client: MistralOcrClient | None = None
    if has_ocr and provider_set is not None:
        try:
            ocr_client = MistralOcrClient(
                provider_set=provider_set,
                cloud_plugin_data_dir=cloud_plugin_data_dir,
                plugin_data_dir=plugin_data_dir,
            )
        except (ValueError, CloudNotEnrolledError):
            has_ocr = False

    for doc in inline:
        content = _decode_base64(doc.content_base64 or "")
        if content is None:
            blocks.append(
                f"### {t(locale, 'attachments.title', name=doc.name)}\n"
                + t(
                    locale,
                    "attachments.unreadable_block",
                    message=t(locale, "attachments.unreadable"),
                )
            )
            statuses.append(_status(doc.id, "unavailable", locale))
            continue

        if _is_image(doc.name, doc.mime_type):
            if provider_set is None:
                blocks.append(
                    f"### {t(locale, 'attachments.title_image', name=doc.name)}\n"
                    + t(
                        locale,
                        "attachments.image",
                        mime=doc.mime_type or t(locale, "attachments.mime_unknown"),
                        size=_format_size(doc.size_bytes, locale),
                    )
                )
                statuses.append(_status(doc.id, "other", locale))
                continue
            if has_vision:
                media_type = _image_media_type(doc.mime_type, doc.name)
                vision_parts.append(
                    BinaryContent(data=content, media_type=media_type)
                )
                blocks.append(
                    f"### {t(locale, 'attachments.title_image', name=doc.name)}\n"
                    + t(locale, "attachments.vision_injected", name=doc.name)
                )
                statuses.append(_status(doc.id, "viewed", locale))
            else:
                blocks.append(
                    f"### {t(locale, 'attachments.title_image', name=doc.name)}\n"
                    + _unavailable_block(doc, locale, locked=locked)
                )
                statuses.append(_status(doc.id, "unavailable", locale))
            continue

        if _is_pdf(doc.name, doc.mime_type):
            if len(content) > limits.extract_max_input_bytes:
                blocks.append(
                    f"### {t(locale, 'attachments.title', name=doc.name)}\n"
                    + t(
                        locale,
                        "attachments.binary_too_large",
                        size=len(content),
                        max_bytes=limits.extract_max_input_bytes,
                    )
                )
                statuses.append(_status(doc.id, "unavailable", locale))
                continue

            scanned = is_scanned_pdf(content)
            if not scanned:
                try:
                    extracted = await extractor.extract(
                        content=content,
                        filename=doc.name,
                        mime_type=doc.mime_type,
                    )
                except Exception as exc:  # noqa: BLE001
                    blocks.append(
                        f"### {t(locale, 'attachments.title', name=doc.name)}\n"
                        + t(locale, "attachments.extraction_failed", error=exc)
                    )
                    statuses.append(_status(doc.id, "unavailable", locale))
                    continue
                note = ""
                if extracted.metadata.get("truncated"):
                    note = t(
                        locale,
                        "attachments.truncated_note",
                        max_chars=limits.extract_max_chars,
                        total=extracted.metadata.get("chars_total", "?"),
                    )
                blocks.append(_format_extracted_document_block(doc, extracted.text, locale, note=note))
                statuses.append(_status(doc.id, "read", locale))
                continue

            if provider_set is None:
                blocks.append(
                    f"### {t(locale, 'attachments.title', name=doc.name)}\n"
                    + t(locale, "attachments.unavailable_guided", name=doc.name)
                )
                statuses.append(_status(doc.id, "unavailable", locale))
                continue

            if has_ocr and ocr_client is not None:
                try:
                    ocr_result = await ocr_client.ocr_pdf(
                        content,
                        max_pages=limits.ocr_max_pages,
                    )
                    text = ocr_result.text
                    if len(text) > limits.extract_max_chars:
                        text = text[: limits.extract_max_chars]
                        text += t(
                            locale,
                            "attachments.text_truncated_suffix",
                            max_chars=limits.extract_max_chars,
                        )
                    blocks.append(_format_extracted_document_block(doc, text, locale))
                    statuses.append(_status(doc.id, "scanned_pdf", locale))
                except Exception as exc:  # noqa: BLE001
                    blocks.append(
                        f"### {t(locale, 'attachments.title', name=doc.name)}\n"
                        + t(locale, "attachments.ocr_failed", error=exc)
                    )
                    statuses.append(_status(doc.id, "unavailable", locale))
                continue

            if has_vision:
                page_images = _pdf_pages_to_images(
                    content,
                    max_pages=limits.ocr_max_pages,
                )
                if page_images:
                    vision_parts.extend(page_images)
                    blocks.append(
                        f"### {t(locale, 'attachments.title', name=doc.name)}\n"
                        + t(locale, "attachments.vision_pdf_injected", name=doc.name)
                    )
                    statuses.append(_status(doc.id, "viewed_pdf", locale))
                else:
                    blocks.append(
                        f"### {t(locale, 'attachments.title', name=doc.name)}\n"
                        + _unavailable_block(doc, locale, locked=locked)
                    )
                    statuses.append(_status(doc.id, "unavailable", locale))
                continue

            blocks.append(
                f"### {t(locale, 'attachments.title', name=doc.name)}\n"
                + _unavailable_block(doc, locale, locked=locked)
            )
            statuses.append(_status(doc.id, "unavailable", locale))
            continue

        if _is_docx(doc.name, doc.mime_type):
            status_key = "word"
        elif _is_xlsx(doc.name, doc.mime_type):
            status_key = "excel"
        else:
            status_key = ""

        if is_binary_document(doc.name, doc.mime_type):
            if len(content) > limits.extract_max_input_bytes:
                blocks.append(
                    f"### {t(locale, 'attachments.title', name=doc.name)}\n"
                    + t(
                        locale,
                        "attachments.binary_too_large",
                        size=len(content),
                        max_bytes=limits.extract_max_input_bytes,
                    )
                )
                statuses.append(_status(doc.id, "unavailable", locale))
                continue
            try:
                extracted = await extractor.extract(
                    content=content,
                    filename=doc.name,
                    mime_type=doc.mime_type,
                )
            except Exception as exc:  # noqa: BLE001
                blocks.append(
                    f"### {t(locale, 'attachments.title', name=doc.name)}\n"
                    + t(locale, "attachments.extraction_failed", error=exc)
                )
                statuses.append(_status(doc.id, "unavailable", locale))
                continue
            note = ""
            if extracted.metadata.get("truncated"):
                note = t(
                    locale,
                    "attachments.truncated_note",
                    max_chars=limits.extract_max_chars,
                    total=extracted.metadata.get("chars_total", "?"),
                )
            blocks.append(_format_extracted_document_block(doc, extracted.text, locale, note=note))
            if status_key:
                statuses.append(_status(doc.id, status_key, locale))
            continue

        if _is_text(doc.name, doc.mime_type):
            try:
                text = content.decode("utf-8", errors="replace")
            except Exception:  # pragma: no cover
                blocks.append(
                    f"### {t(locale, 'attachments.title', name=doc.name)}\n"
                    + t(locale, "attachments.text_decode_failed")
                )
                statuses.append(_status(doc.id, "unavailable", locale))
                continue
            if len(text) > limits.extract_max_chars:
                text = text[: limits.extract_max_chars]
                text += t(
                    locale,
                    "attachments.text_truncated_suffix",
                    max_chars=limits.extract_max_chars,
                )
            blocks.append(_format_extracted_document_block(doc, text, locale))
            statuses.append(_status(doc.id, "read", locale))
            continue

        blocks.append(
            f"### {t(locale, 'attachments.title', name=doc.name)}\n"
            + t(
                locale,
                "attachments.unsupported_type",
                mime=doc.mime_type or t(locale, "attachments.mime_unknown"),
            )
        )
        statuses.append(_status(doc.id, "unavailable", locale))

    context_text = ""
    if blocks:
        context_text = t(locale, "attachments.header") + "\n\n" + "\n\n".join(blocks)

    return ProcessedAttachments(
        context_text=context_text,
        vision_parts=vision_parts,
        statuses=statuses,
    )


async def build_inline_attachments_context(
    documents: list[DocumentReference],
    limits: Limits,
    locale: str = DEFAULT_LOCALE,
    provider_set: ProviderSet | None = None,
    ui_mode: str = "guided",
) -> str:
    """Rétrocompat : retourne uniquement le bloc texte du contexte."""
    result = await process_inline_attachments(
        documents,
        limits,
        locale=locale,
        provider_set=provider_set,
        ui_mode=ui_mode,
    )
    return result.context_text


def build_user_prompt(
    message: str,
    processed: ProcessedAttachments,
) -> str | list[Any]:
    """Construit le prompt utilisateur (texte seul ou multimodal avec vision)."""
    if not processed.vision_parts:
        if processed.context_text:
            return f"{processed.context_text}\n\n{message}"
        return message

    parts: list[Any] = []
    if processed.context_text:
        parts.append(processed.context_text)
    parts.extend(processed.vision_parts)
    if message.strip():
        parts.append(message)
    return parts


__all__ = [
    "AttachmentStatusInfo",
    "ProcessedAttachments",
    "ReprocessAttachmentResult",
    "attachment_relative_path",
    "attachment_status_label",
    "build_inline_attachments_context",
    "build_user_prompt",
    "persist_attachment_file",
    "process_inline_attachments",
    "reprocess_attachment",
]
