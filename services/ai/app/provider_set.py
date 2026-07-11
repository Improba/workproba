"""Facade ProviderSet partagée (sidecar LLM + routage pièces jointes / OCR)."""

from __future__ import annotations

from typing import Any

from app.schemas import (
    ProviderSet,
    ProviderSetCapabilities,
    ProviderSetOcr,
    ProviderSetVision,
)

# Alias rétrocompat agent H (attachments, OCR).
OcrConfig = ProviderSetOcr
VisionConfig = ProviderSetVision
ProviderCapabilities = ProviderSetCapabilities


def resolve_provider_set(raw: Any) -> ProviderSet | None:
    if raw is None:
        return None
    if isinstance(raw, ProviderSet):
        return raw
    if isinstance(raw, dict):
        return ProviderSet.model_validate(raw)
    return None


def vision_available(provider_set: ProviderSet | None) -> bool:
    if provider_set is None:
        return False
    return (
        provider_set.capabilities.vision
        and provider_set.vision.mode == "chat"
    )


def ocr_provider_implemented(provider: str) -> bool:
    """Providers OCR réellement implémentés côté sidecar (Docling = à venir)."""
    normalized = (provider or "").strip().lower()
    return normalized == "mistral"


def ocr_available(provider_set: ProviderSet | None) -> bool:
    if provider_set is None:
        return False
    ocr = provider_set.ocr
    if ocr is None:
        return False
    if ocr.mode == "none":
        return False
    provider = (ocr.provider or "").strip().lower()
    if provider in {"", "none"}:
        return False
    return ocr_provider_implemented(provider)


def is_locked_mode(provider_set: ProviderSet | None, ui_mode: str) -> bool:
    if ui_mode == "locked":
        return True
    if provider_set is not None and provider_set.ui_mode_locked:
        return True
    return False


__all__ = [
    "OcrConfig",
    "ProviderCapabilities",
    "ProviderSet",
    "VisionConfig",
    "is_locked_mode",
    "ocr_available",
    "ocr_provider_implemented",
    "resolve_provider_set",
    "vision_available",
]
