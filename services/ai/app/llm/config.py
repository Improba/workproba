from __future__ import annotations

from typing import Any

from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from app.config import ProviderName
from app.schemas import LLMProviderConfig

# Base URL par défaut selon le provider (quand non fourni par la config).
_DEFAULT_BASE_URL: dict[str, str] = {
    "mistral": "https://api.mistral.ai/v1",
    "ollama": "http://127.0.0.1:11434/v1",
}

# Providers routés via l'API OpenAI-compat (un seul client modèle couvre
# OpenAI, Ollama, vLLM, Mistral-compat). Anthropic a sa propre API.
_OPENAI_COMPAT_PROVIDERS: frozenset[ProviderName] = frozenset(
    {"openai", "openai_compat", "ollama", "vllm", "mistral"}
)


def resolve_llm_config(
    request_config: LLMProviderConfig | None,
    settings: Any,
) -> LLMProviderConfig:
    """Prefer the per-turn config from the request, then environment fallbacks."""

    if request_config is not None:
        return request_config

    return LLMProviderConfig(
        provider=settings.llm_default_provider,
        model=settings.llm_default_model,
        base_url=settings.llm_default_base_url,
        api_key=settings.llm_default_api_key,
    )


def build_model(config: LLMProviderConfig) -> Model:
    """Construit un modèle Pydantic AI natif depuis la config métier."""
    api_key = config.api_key.get_secret_value() if config.api_key else None
    provider = config.provider

    if provider in _OPENAI_COMPAT_PROVIDERS:
        base_url = config.base_url or _DEFAULT_BASE_URL.get(provider)
        # Ollama ignore l'API key mais le client OpenAI peut exiger une valeur non-nulle.
        effective_key = api_key if api_key is not None else ("ollama" if provider == "ollama" else None)

        return OpenAIChatModel(
            model_name=config.model,
            provider=OpenAIProvider(base_url=base_url, api_key=effective_key),
        )

    if provider == "anthropic":
        try:
            from pydantic_ai.models.anthropic import AnthropicModel
            from pydantic_ai.providers.anthropic import AnthropicProvider
        except ImportError as exc:  # pragma: no cover - optional dep
            raise RuntimeError(
                "Provider anthropic non disponible : installez 'anthropic' "
                "(pip install \"pydantic-ai-slim[anthropic]\")."
            ) from exc
        return AnthropicModel(
            model_name=config.model,
            provider=AnthropicProvider(api_key=api_key, base_url=config.base_url),
        )

    raise ValueError(f"Provider LLM non supporté : {provider}")


def build_model_settings(config: LLMProviderConfig) -> ModelSettings:
    settings: ModelSettings = {}
    if config.temperature is not None:
        settings["temperature"] = config.temperature
    if config.max_tokens is not None:
        settings["max_tokens"] = config.max_tokens
    if config.extra_headers:
        settings["extra_headers"] = dict(config.extra_headers)
    return settings
