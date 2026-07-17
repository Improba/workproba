"""Classification des erreurs provider éligibles au repli chat."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded

try:
    from openai import (
        APIConnectionError as OpenAIAPIConnectionError,
    )
    from openai import (
        APITimeoutError as OpenAIAPITimeoutError,
    )
    from openai import (
        APIStatusError as OpenAIAPIStatusError,
    )
    from openai import (
        AuthenticationError as OpenAIAuthenticationError,
    )
    from openai import (
        InternalServerError as OpenAIInternalServerError,
    )
    from openai import (
        PermissionDeniedError as OpenAIPermissionDeniedError,
    )
    from openai import (
        RateLimitError as OpenAIRateLimitError,
    )
except ImportError:  # pragma: no cover
    OpenAIAPITimeoutError = ()  # type: ignore[misc, assignment]
    OpenAIAPIConnectionError = ()  # type: ignore[misc, assignment]
    OpenAIInternalServerError = ()  # type: ignore[misc, assignment]
    OpenAIRateLimitError = ()  # type: ignore[misc, assignment]
    OpenAIAuthenticationError = ()  # type: ignore[misc, assignment]
    OpenAIPermissionDeniedError = ()  # type: ignore[misc, assignment]
    OpenAIAPIStatusError = ()  # type: ignore[misc, assignment]

try:
    from anthropic import (
        APIConnectionError as AnthropicAPIConnectionError,
    )
    from anthropic import (
        APITimeoutError as AnthropicAPITimeoutError,
    )
    from anthropic import (
        APIStatusError as AnthropicAPIStatusError,
    )
    from anthropic import (
        AuthenticationError as AnthropicAuthenticationError,
    )
    from anthropic import (
        InternalServerError as AnthropicInternalServerError,
    )
    from anthropic import (
        PermissionDeniedError as AnthropicPermissionDeniedError,
    )
    from anthropic import (
        RateLimitError as AnthropicRateLimitError,
    )
except ImportError:  # pragma: no cover
    AnthropicAPITimeoutError = ()  # type: ignore[misc, assignment]
    AnthropicAPIConnectionError = ()  # type: ignore[misc, assignment]
    AnthropicInternalServerError = ()  # type: ignore[misc, assignment]
    AnthropicRateLimitError = ()  # type: ignore[misc, assignment]
    AnthropicAuthenticationError = ()  # type: ignore[misc, assignment]
    AnthropicPermissionDeniedError = ()  # type: ignore[misc, assignment]
    AnthropicAPIStatusError = ()  # type: ignore[misc, assignment]

_TIMEOUT_TYPES: tuple[type[BaseException], ...] = (
    OpenAIAPITimeoutError,
    AnthropicAPITimeoutError,
    httpx.TimeoutException,
)

_CONNECTION_TYPES: tuple[type[BaseException], ...] = (
    OpenAIAPIConnectionError,
    AnthropicAPIConnectionError,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
)

_RATE_LIMIT_TYPES: tuple[type[BaseException], ...] = (
    OpenAIRateLimitError,
    AnthropicRateLimitError,
)

_SERVER_ERROR_TYPES: tuple[type[BaseException], ...] = (
    OpenAIInternalServerError,
    AnthropicInternalServerError,
)

_AUTH_TYPES: tuple[type[BaseException], ...] = (
    OpenAIAuthenticationError,
    OpenAIPermissionDeniedError,
    AnthropicAuthenticationError,
    AnthropicPermissionDeniedError,
)

_NON_FALLBACKABLE_TYPES: tuple[type[BaseException], ...] = (
    UsageLimitExceeded,
    UnexpectedModelBehavior,
    asyncio.CancelledError,
    *_AUTH_TYPES,
)

from app.llm.cloud_errors import parse_cloud_llm_error_code  # noqa: E402


class FallbackableProviderError(Exception):
    """Erreur provider éligible au repli, propagée vers main.py."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _status_code(exc: BaseException) -> int | None:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code
    response = getattr(exc, "response", None)
    if response is not None:
        code = getattr(response, "status_code", None)
        if isinstance(code, int):
            return code
    return None


def _classify_single(exc: BaseException) -> tuple[bool, str]:
    if isinstance(exc, _NON_FALLBACKABLE_TYPES):
        return False, ""

    if isinstance(exc, _TIMEOUT_TYPES):
        return True, "timeout"

    if isinstance(exc, _CONNECTION_TYPES):
        return True, "connection"

    if isinstance(exc, _RATE_LIMIT_TYPES):
        return True, "http_429"

    if isinstance(exc, _SERVER_ERROR_TYPES):
        return True, "http_5xx"

    status_code = _status_code(exc)
    if status_code == 429:
        return True, "http_429"
    if status_code is not None and status_code >= 500:
        return True, "http_5xx"

    if isinstance(exc, (OpenAIAPIStatusError, AnthropicAPIStatusError)):
        if status_code == 429:
            return True, "http_429"
        if status_code is not None and status_code >= 500:
            return True, "http_5xx"

    return False, ""


def is_fallbackable(exc: BaseException) -> tuple[bool, str]:
    """Indique si une exception autorise un repli provider avant tout contenu émis.

    Remonte la chaîne ``__cause__`` puis ``__context__``. Un type non éligible
    au repli court-circuite immédiatement la remontée (même si son contexte
    serait fallbackable).
    """
    if parse_cloud_llm_error_code(exc):
        return False, ""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, _NON_FALLBACKABLE_TYPES):
            return False, ""
        ok, reason = _classify_single(current)
        if ok:
            return True, reason
        current = current.__cause__ or current.__context__
    return False, ""
