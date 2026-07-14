"""Recherche web déléguée (Mistral Conversations API)."""

from app.web_search.engine import search_web, set_search_backend
from app.web_search.errors import WebSearchError, web_search_error_detail
from app.web_search.support import web_search_available

__all__ = [
    "WebSearchError",
    "search_web",
    "set_search_backend",
    "web_search_available",
    "web_search_error_detail",
]
