"""Recherche web déléguée (backends pluggables)."""

from app.web_search.backends import (
    clear_web_search_backends,
    register_web_search_backend,
    resolve_web_search_backend,
)
from app.web_search.engine import search_web, set_search_backend
from app.web_search.errors import WebSearchError, web_search_error_detail
from app.web_search.support import web_search_available

__all__ = [
    "WebSearchError",
    "clear_web_search_backends",
    "register_web_search_backend",
    "resolve_web_search_backend",
    "search_web",
    "set_search_backend",
    "web_search_available",
    "web_search_error_detail",
]
