"""Disponibilité recherche web selon le contexte de tour."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.web_search.backends import resolve_web_search_backend

if TYPE_CHECKING:
    from app.agent.tools import ToolContext


def web_search_available(context: ToolContext) -> bool:
    """True si le réseau est autorisé et qu'un backend existe pour le provider actif."""
    if not context.permissions_network:
        return False
    provider_set = context.provider_set
    if provider_set is None or provider_set.chat is None:
        return False
    provider = provider_set.chat.provider
    return bool(provider and resolve_web_search_backend(provider) is not None)
