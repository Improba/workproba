from __future__ import annotations

from typing import Any

from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from app.config import ProviderName
from app.llm.mistral import MistralChatModel
from app.llm.provider_sets import resolve_chat_from_set, supported_reasoning_efforts_for_set
from app.schemas import LLMProviderConfig, ProviderSet, ReasoningEffort

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
    provider_set: ProviderSet | None = None,
) -> LLMProviderConfig:
    """Priorise le set actif, puis la config par tour, puis l'environnement."""

    if provider_set is not None:
        return resolve_chat_from_set(provider_set)

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

        model_cls: type[OpenAIChatModel] = MistralChatModel if provider == "mistral" else OpenAIChatModel
        # Mistral : replay multi-turn du thinking en mode tags déterministe
        # (voir app.llm.mistral + test live multi-turn).
        profile = {"openai_chat_send_back_thinking_parts": "tags"} if provider == "mistral" else None
        return model_cls(
            model_name=config.model,
            provider=OpenAIProvider(base_url=base_url, api_key=effective_key),
            profile=profile,
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


def reasoning_effort_for(config: LLMProviderConfig) -> ReasoningEffort | None:
    """Effort de raisonnement effectif (None si absent ou ``none``)."""
    effort = config.reasoning_effort
    if effort is None or effort == "none":
        return None
    return effort


def _mistral_supports_reasoning(model: str) -> bool:
    """True si le modèle Mistral accepte ``reasoning_effort`` (none/high)."""
    normalized = (model or "").strip().lower()
    if any(
        token in normalized
        for token in (
            "mistral-small-latest",
            "mistral-medium-3-5",
            "mistral-medium-latest",
        )
    ):
        return True
    if "medium" in normalized and "-latest" in normalized:
        return True
    if "small" in normalized and "-latest" in normalized:
        return True
    return False


# Efforts réellement acceptés par l'API du provider pour un modèle donné.
# L'API Mistral n'accepte que `none`/`high` pour les modèles à raisonnement ajustable
# (`mistral-small-latest`, `mistral-medium-3-5`, alias `mistral-medium-latest`).
# ici en sécurité même si le front a déjà clampe, pour ne jamais planter l'appel.
def _supported_efforts(provider: ProviderName, model: str) -> tuple[ReasoningEffort, ...]:
    if provider == "mistral":
        if _mistral_supports_reasoning(model):
            return ("none", "high")
        return ("none",)
    if provider == "anthropic":
        return ("none", "low", "medium", "high")
    # openai / openai_compat / ollama / vllm
    return ("none", "low", "medium", "high")


def clamp_reasoning_effort(
    provider: ProviderName,
    model: str,
    effort: ReasoningEffort | None,
    provider_set: ProviderSet | None = None,
) -> ReasoningEffort | None:
    """Ramène un effort à une valeur supportée par le couple provider/modèle.

    Retourne None pour `none` ou absence. Si l'effort n'est pas supporté, on
    tombe sur `high` (effort non-nul garanti pour les modèles Mistral binaires)
    plutôt que d'envoyer une valeur refusée par l'API.
    """
    if effort is None or effort == "none":
        return None
    set_efforts = supported_reasoning_efforts_for_set(provider_set, model)
    supported = set_efforts if set_efforts is not None else _supported_efforts(provider, model)
    if effort in supported:
        return effort
    return "high" if "high" in supported else None


def build_model_settings(
    config: LLMProviderConfig,
    provider_set: ProviderSet | None = None,
) -> ModelSettings:
    settings: ModelSettings = {}
    if config.temperature is not None:
        settings["temperature"] = config.temperature
    if config.max_tokens is not None:
        settings["max_tokens"] = config.max_tokens
    if config.extra_headers:
        settings["extra_headers"] = dict(config.extra_headers)

    provider = config.provider
    effort = clamp_reasoning_effort(provider, config.model, config.reasoning_effort, provider_set)
    if effort is not None:
        if provider in _OPENAI_COMPAT_PROVIDERS:
            settings["openai_reasoning_effort"] = effort
        elif provider == "anthropic":
            settings["thinking"] = effort

    # Note : le replay multi-turn du thinking est contrôlé par le *profile* du
    # modèle (openai_chat_send_back_thinking_parts), pas par ModelSettings.
    # MistralChatModel active le mode 'tags' via son profile (voir build_model).

    return settings
