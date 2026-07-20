"""Codes machine des erreurs LLM cloud (proxy /llm/v1)."""

from __future__ import annotations

import json
from typing import Any

from app.i18n import t

KNOWN_CLOUD_LLM_CODES = frozenset(
    {
        "cloud_not_enrolled",
        "not_subscribed",
        "quota_exceeded",
        "cloud_unreachable",
        "mistral_unavailable",
        "mistral_timeout",
        "mistral_upstream_error",
        "unsupported_model",
        "bad_request",
        "bearer_token_required",
        "invalid_user_jwt",
        "invalid_device_token",
        "device_organization_required",
        "org_id_required",
    }
)

NON_RETRYABLE_CLOUD_LLM_CODES = KNOWN_CLOUD_LLM_CODES

MISTRAL_OUTAGE_CODES = frozenset(
    {
        "mistral_unavailable",
        "mistral_timeout",
        "mistral_upstream_error",
    }
)


def is_known_cloud_llm_code(code: str) -> bool:
    return code in KNOWN_CLOUD_LLM_CODES


def is_non_retryable_cloud_llm_code(code: str) -> bool:
    return code in NON_RETRYABLE_CLOUD_LLM_CODES


def _extract_message_from_payload(payload: Any) -> str | None:
    if isinstance(payload, str):
        stripped = payload.strip()
        return stripped or None
    if not isinstance(payload, dict):
        return None
    for key in ("message", "detail", "error", "code"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = _extract_message_from_payload(value)
            if nested:
                return nested
    return None


def _code_from_response_payload(payload: Any) -> str | None:
    message = _extract_message_from_payload(payload)
    if message and is_known_cloud_llm_code(message):
        return message
    return None


def _code_from_exception(exc: BaseException) -> str | None:
    body = getattr(exc, "body", None)
    if body is not None:
        code = _code_from_response_payload(body)
        if code:
            return code

    response = getattr(exc, "response", None)
    if response is not None:
        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError, AttributeError):
            payload = None
        if payload is not None:
            code = _code_from_response_payload(payload)
            if code:
                return code

    if exc.__class__.__name__ == "CloudNotEnrolledError":
        return "cloud_not_enrolled"

    return None


def parse_cloud_llm_error_code(exc: BaseException) -> str | None:
    """Extrait un code machine cloud depuis une exception (OpenAI SDK, httpx, etc.)."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        code = _code_from_exception(current)
        if code:
            return code
        current = current.__cause__ or current.__context__
    return None


def cloud_llm_error_message(code: str, locale: str) -> str:
    key = f"loop.cloud_llm.{code}"
    message = t(locale, key)
    if message != key:
        return message
    if code in MISTRAL_OUTAGE_CODES:
        fallback = t(locale, "loop.cloud_llm.mistral_unavailable")
        if fallback != "loop.cloud_llm.mistral_unavailable":
            return fallback
    return t(locale, "loop.provider_unavailable")
