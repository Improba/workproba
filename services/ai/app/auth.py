from secrets import compare_digest
from typing import Awaitable, Callable

from fastapi import Request, Response, status
from pydantic import ValidationError
from starlette.responses import JSONResponse

from app.config import get_settings
from app.i18n import DEFAULT_LOCALE, t


INTERNAL_SECRET_HEADER = "X-Internal-Secret"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def is_loopback_host(host: str) -> bool:
    return host in LOOPBACK_HOSTS


async def internal_secret_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Sidecar desktop : loopback uniquement, secret interne requis si configuré."""

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
            content={"detail": t(DEFAULT_LOCALE, "auth.local_only")},
        )

    expected_secret = settings.internal_secret
    provided_secret = request.headers.get(INTERNAL_SECRET_HEADER)

    # Mode permissif uniquement si le secret est explicitement vide ET env dev.
    if not expected_secret:
        if settings.is_dev:
            return await call_next(request)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Internal service secret is not configured."},
        )

    if not provided_secret or not compare_digest(provided_secret, expected_secret):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid internal service secret."},
        )

    return await call_next(request)
