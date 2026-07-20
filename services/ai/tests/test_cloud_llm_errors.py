"""Tests du mapping des erreurs LLM cloud."""

from __future__ import annotations

import httpx
import pytest
from openai import AuthenticationError, PermissionDeniedError, RateLimitError
from pydantic_ai.exceptions import ModelHTTPError

from app.llm.cloud_errors import (
    cloud_llm_error_message,
    is_non_retryable_cloud_llm_code,
    parse_cloud_llm_error_code,
)
from app.llm.fallback import is_fallbackable
from app.llm.provider_sets import CloudNotEnrolledError


def _httpx_request() -> httpx.Request:
    return httpx.Request("POST", "https://cloud.test/llm/v1/chat/completions")


def test_parse_cloud_code_from_openai_body() -> None:
    exc = RateLimitError(
        "quota_exceeded",
        response=httpx.Response(
            429,
            request=_httpx_request(),
            json={"statusCode": 429, "message": "quota_exceeded"},
        ),
        body={"message": "quota_exceeded"},
    )
    assert parse_cloud_llm_error_code(exc) == "quota_exceeded"


def test_parse_cloud_code_from_permission_denied() -> None:
    exc = PermissionDeniedError(
        "not_subscribed",
        response=httpx.Response(
            403,
            request=_httpx_request(),
            json={"statusCode": 403, "message": "not_subscribed"},
        ),
        body={"message": "not_subscribed"},
    )
    assert parse_cloud_llm_error_code(exc) == "not_subscribed"


def test_parse_cloud_not_enrolled_from_value_error() -> None:
    assert parse_cloud_llm_error_code(CloudNotEnrolledError()) == "cloud_not_enrolled"


def test_cloud_codes_are_non_retryable() -> None:
    assert is_non_retryable_cloud_llm_code("quota_exceeded")
    exc = RateLimitError(
        "quota_exceeded",
        response=httpx.Response(
            429,
            request=_httpx_request(),
            json={"message": "quota_exceeded"},
        ),
        body={"message": "quota_exceeded"},
    )
    assert is_fallbackable(exc) == (False, "")


def test_parse_invalid_user_jwt_from_authentication_error() -> None:
    exc = AuthenticationError(
        "invalid_user_jwt",
        response=httpx.Response(
            401,
            request=_httpx_request(),
            json={"statusCode": 401, "message": "invalid_user_jwt"},
        ),
        body={"message": "invalid_user_jwt"},
    )
    assert parse_cloud_llm_error_code(exc) == "invalid_user_jwt"


def test_invalid_user_jwt_is_non_retryable_and_not_fallbackable() -> None:
    assert is_non_retryable_cloud_llm_code("invalid_user_jwt")
    exc = AuthenticationError(
        "invalid_user_jwt",
        response=httpx.Response(
            401,
            request=_httpx_request(),
            json={"message": "invalid_user_jwt"},
        ),
        body={"message": "invalid_user_jwt"},
    )
    assert is_fallbackable(exc) == (False, "")


def test_parse_invalid_user_jwt_from_model_http_error_cause() -> None:
    auth_exc = AuthenticationError(
        "invalid_user_jwt",
        response=httpx.Response(
            401,
            request=_httpx_request(),
            json={"message": "invalid_user_jwt"},
        ),
        body={"message": "invalid_user_jwt"},
    )
    exc = ModelHTTPError(401, "mistral-large", body="Unauthorized")
    exc.__cause__ = auth_exc
    assert parse_cloud_llm_error_code(exc) == "invalid_user_jwt"


def test_invalid_user_jwt_message_localized() -> None:
    message = cloud_llm_error_message("invalid_user_jwt", "fr")
    assert "session" in message.lower()
    assert "reconnect" in message.lower()


def test_cloud_llm_error_message_localized() -> None:
    message = cloud_llm_error_message("quota_exceeded", "fr")
    assert "quota" in message.lower()


@pytest.mark.parametrize(
    ("code",),
    [
        ("mistral_unavailable",),
        ("mistral_timeout",),
        ("mistral_upstream_error",),
    ],
)
def test_mistral_outage_messages_share_fallback(code: str) -> None:
    message = cloud_llm_error_message(code, "en")
    assert "unavailable" in message.lower()
