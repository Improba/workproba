"""Registre de backends de recherche web (pluggable par provider)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.limits import Limits
from app.schemas import ProviderSet

WebSearchBackend = Callable[
    [str],
    Awaitable[dict[str, Any]],
]

# Signature étendue attendue en pratique :
# async def backend(query, *, provider_set, locale, limits, premium=False) -> dict

_BACKEND_REGISTRY: dict[str, WebSearchBackend] = {}


def register_web_search_backend(
    provider: str,
    backend: WebSearchBackend,
) -> None:
    """Enregistre un backend pour un provider (ex. mistral, openai)."""
    _BACKEND_REGISTRY[provider.strip().lower()] = backend


def unregister_web_search_backend(provider: str) -> None:
    _BACKEND_REGISTRY.pop(provider.strip().lower(), None)


def clear_web_search_backends() -> None:
    _BACKEND_REGISTRY.clear()


def resolve_web_search_backend(provider: str | None) -> WebSearchBackend | None:
    if not provider:
        return None
    return _BACKEND_REGISTRY.get(provider.strip().lower())


async def run_registered_backend(
    provider: str,
    query: str,
    *,
    provider_set: ProviderSet | None,
    locale: str,
    limits: Limits,
    premium: bool = False,
) -> dict[str, Any]:
    backend = resolve_web_search_backend(provider)
    if backend is None:
        raise KeyError(provider)
    return await backend(
        query,
        provider_set=provider_set,
        locale=locale,
        limits=limits,
        premium=premium,
    )
