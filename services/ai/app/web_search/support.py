"""Disponibilité recherche web selon le contexte de tour."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agent.tools import ToolContext


def web_search_available(context: ToolContext) -> bool:
    """True si le set actif est Mistral et que le réseau est autorisé."""
    if not context.permissions_network:
        return False
    provider_set = context.provider_set
    if provider_set is None or provider_set.chat is None:
        return False
    return provider_set.chat.provider == "mistral"
