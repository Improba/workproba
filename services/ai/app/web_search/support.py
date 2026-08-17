"""Disponibilité recherche web selon le contexte de tour."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from app.web_search.backends import resolve_web_search_backend
from app.web_search.cloud_backend import cloud_search_ready
from app.web_search.tavily_backend import resolve_tavily_api_key

if TYPE_CHECKING:
    from app.agent.tools import ToolContext


def provider_has_web_search_backend(provider: str) -> bool:
    normalized = provider.strip().lower()
    if normalized == "mistral":
        return resolve_web_search_backend("mistral") is not None
    if normalized in {"ollama", "tavily"}:
        return bool(resolve_tavily_api_key())
    return resolve_web_search_backend(normalized) is not None


def resolve_web_search_cloud_dir(context: ToolContext) -> Path | None:
    """Même résolution que le tour agent (`resolve_plugin_data_dir`)."""
    from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD, resolve_plugin_data_dir

    if context.cloud_plugin_data_dir is not None:
        return context.cloud_plugin_data_dir
    return resolve_plugin_data_dir(PLUGIN_WORKPROBA_CLOUD, context.plugin_data_dir)


def web_search_available(context: ToolContext) -> bool:
    """True si le réseau est autorisé et qu'un backend utilisable existe."""
    if not context.permissions_network:
        return False
    provider_set = context.provider_set
    if provider_set is None or provider_set.chat is None:
        return False
    if provider_set.auth_mode == "device_bearer":
        return cloud_search_ready(resolve_web_search_cloud_dir(context))
    provider = provider_set.chat.provider
    if not provider:
        return False
    if provider_has_web_search_backend(provider):
        return True
    if provider.strip().lower() == "mistral" and resolve_tavily_api_key():
        return True
    return False
