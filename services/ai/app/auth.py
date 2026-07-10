from secrets import compare_digest
from typing import Awaitable, Callable

from fastapi import Request, Response, status
from pydantic import ValidationError
from starlette.responses import JSONResponse

from app.config import get_settings


INTERNAL_SECRET_HEADER = "X-Internal-Secret"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def is_loopback_host(host: str) -> bool:
    return host in LOOPBACK_HOSTS


async def internal_secret_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Sidecar desktop : loopback uniquement, secret optionnel."""

    if request.method == "GET" and request.url.path in {"/", "/health"}:
        return await call_next(request)

    try:
        settings = get_settings()
    except ValidationError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Internal service secret is not configured."},
        )

    client_host = request.client.host if request.client else ""
    if not is_loopback_host(client_host):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Sidecar accessible uniquement en local."},
        )

    expected_secret = settings.internal_secret
    provided_secret = request.headers.get(INTERNAL_SECRET_HEADER)
    secret_matches = bool(
        expected_secret
        and provided_secret
        and compare_digest(provided_secret, expected_secret)
    )

    if not provided_secret or secret_matches:
        return await call_next(request)

    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": "Invalid internal service secret."},
    )
