"""Provider sets : résolution chat/embeddings/vision depuis un set unifié."""

from __future__ import annotations

from pydantic import SecretStr

from app.schemas import (
    LLMProviderConfig,
    ProviderSet,
    ProviderSetCapabilities,
    ProviderSetChat,
    ProviderSetChatModel,
    ProviderSetEmbeddings,
    ProviderSetOcr,
    ProviderSetVision,
    ReasoningEffort,
)

MISTRAL_DEFAULT_BASE_URL = "https://api.mistral.ai/v1"
OLLAMA_DEFAULT_BASE_URL = "http://127.0.0.1:11434/v1"

MISTRAL_CHAT_MODELS: tuple[ProviderSetChatModel, ...] = (
    ProviderSetChatModel(
        model="mistral-small-latest",
        label="Mistral Small",
        hint="Hybride : chat, code et raisonnement à la demande. Rapide et économique.",
        context_window=256000,
        reasoning_efforts=["none", "high"],
    ),
    ProviderSetChatModel(
        model="mistral-medium-latest",
        label="Mistral Medium",
        hint="Modèle frontier pour agents, code long et workflows multi-étapes.",
        context_window=256000,
        reasoning_efforts=["none", "high"],
    ),
    ProviderSetChatModel(
        model="mistral-large-latest",
        label="Mistral Large",
        hint="Flagship multilingue et multimodal. Qualité maximale.",
        context_window=256000,
        reasoning_efforts=["none"],
    ),
)

MISTRAL_BUILTIN_SET = ProviderSet(
    id="mistral-default",
    name="Mistral",
    description="Cloud Improba, tout-intégré. Chat, vision, OCR, embeddings.",
    badges=["Cloud Improba", "Recommandé"],
    chat=ProviderSetChat(
        provider="mistral",
        model="mistral-small-latest",
        base_url=MISTRAL_DEFAULT_BASE_URL,
        api_key_ref="secrets/mistral",
        reasoning="auto",
        models=list(MISTRAL_CHAT_MODELS),
    ),
    embeddings=ProviderSetEmbeddings(
        provider="mistral",
        model="mistral-embed",
        base_url=MISTRAL_DEFAULT_BASE_URL,
        api_key_ref="secrets/mistral",
    ),
    ocr=ProviderSetOcr(provider="mistral", mode="auto"),
    vision=ProviderSetVision(mode="chat"),
    capabilities=ProviderSetCapabilities(
        reasoning="medium",
        vision=True,
        tools=True,
        web_search=True,
    ),
    is_default=True,
    is_builtin=True,
)

OLLAMA_BUILTIN_SET = ProviderSet(
    id="ollama-local",
    name="Ollama local",
    description="100 % local. Chat et embeddings sur votre machine.",
    badges=["100 % local"],
    chat=ProviderSetChat(
        provider="ollama",
        model="llama3.2",
        base_url=OLLAMA_DEFAULT_BASE_URL,
        reasoning="auto",
    ),
    embeddings=ProviderSetEmbeddings(
        provider="ollama",
        model="nomic-embed-text",
        base_url=OLLAMA_DEFAULT_BASE_URL,
    ),
    ocr=None,
    vision=ProviderSetVision(mode="chat"),
    capabilities=ProviderSetCapabilities(
        reasoning="low",
        vision=False,
        tools=True,
        web_search=True,
    ),
    is_default=False,
    is_builtin=True,
)

BUILTIN_PROVIDER_SETS: tuple[ProviderSet, ...] = (MISTRAL_BUILTIN_SET, OLLAMA_BUILTIN_SET)

_LOCAL_PROVIDERS = frozenset({"ollama", "vllm"})


class MissingApiKeyError(ValueError):
    """Clé API cloud absente du provider set."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(
            f"Clé API manquante pour le provider {provider}. "
            "Renseignez-la dans Réglages → Modèles IA."
        )


def provider_requires_api_key(provider: str) -> bool:
    return provider not in _LOCAL_PROVIDERS


def _chat_reasoning_to_effort(reasoning: str) -> ReasoningEffort | None:
    if reasoning == "auto":
        return None
    if reasoning in ("none", "low", "medium", "high"):
        return reasoning  # type: ignore[return-value]
    return None


def _resolve_api_key(
    chat_or_embed: ProviderSetChat | ProviderSetEmbeddings,
    *,
    fallback_key: SecretStr | None = None,
) -> SecretStr | None:
    if chat_or_embed.api_key is not None:
        raw = chat_or_embed.api_key.get_secret_value().strip()
        if raw:
            return chat_or_embed.api_key
    if fallback_key is not None:
        raw = fallback_key.get_secret_value().strip()
        if raw:
            return fallback_key
    if provider_requires_api_key(chat_or_embed.provider):
        raise MissingApiKeyError(chat_or_embed.provider)
    return None


def resolve_chat_from_set(provider_set: ProviderSet) -> LLMProviderConfig:
    """Construit une config LLM chat depuis le sous-bloc chat du set."""
    chat = provider_set.chat
    if chat is None:
        raise ValueError("Provider set sans configuration chat")
    return LLMProviderConfig(
        provider=chat.provider,
        model=chat.model,
        base_url=chat.base_url,
        api_key=_resolve_api_key(chat),
        reasoning_effort=_chat_reasoning_to_effort(chat.reasoning),
    )


def resolve_fallback_chat_config(provider_set: ProviderSet) -> LLMProviderConfig | None:
    """Construit la config chat de repli, ou None si absente ou non utilisable."""
    chat_fallback = provider_set.chat_fallback
    if chat_fallback is None:
        return None
    chat_key = provider_set.chat.api_key if provider_set.chat else None
    try:
        api_key = _resolve_api_key(chat_fallback, fallback_key=chat_key)
    except MissingApiKeyError:
        return None
    return LLMProviderConfig(
        provider=chat_fallback.provider,
        model=chat_fallback.model,
        base_url=chat_fallback.base_url,
        api_key=api_key,
        reasoning_effort=_chat_reasoning_to_effort(chat_fallback.reasoning),
    )


def resolve_embeddings_from_set(provider_set: ProviderSet) -> LLMProviderConfig | None:
    """Construit une config embeddings depuis le set, ou None si absent."""
    if provider_set.embeddings is None:
        return None
    embed = provider_set.embeddings
    chat_key = provider_set.chat.api_key if provider_set.chat else None
    return LLMProviderConfig(
        provider=embed.provider,
        model=embed.model,
        base_url=embed.base_url,
        api_key=_resolve_api_key(embed, fallback_key=chat_key),
    )


def resolve_vision_mode(provider_set: ProviderSet) -> str:
    """Mode vision effectif du set (``chat`` ou ``none``)."""
    return provider_set.vision.mode


def set_capabilities(provider_set: ProviderSet) -> ProviderSetCapabilities:
    """Capacités effectives du set (reasoning, vision, tools, web_search)."""
    caps = provider_set.capabilities.model_copy()
    if caps.web_search:
        return caps
    chat = provider_set.chat
    if chat and chat.provider:
        from app.web_search.support import provider_has_web_search_backend

        if provider_has_web_search_backend(chat.provider):
            return caps.model_copy(update={"web_search": True})
    return caps


def web_search_is_supported(provider_set: ProviderSet) -> bool:
    return set_capabilities(provider_set).web_search


def ocr_is_supported(provider_set: ProviderSet) -> bool:
    from app.provider_set import ocr_available

    return ocr_available(provider_set)


def supported_reasoning_efforts_for_set(
    provider_set: ProviderSet | None,
    model: str,
) -> tuple[ReasoningEffort, ...] | None:
    """Efforts déclarés dans le catalogue du set, ou None si absent."""
    chat = provider_set.chat if provider_set else None
    if not chat or not chat.models:
        return None
    normalized = (model or "").strip().lower()
    for entry in chat.models:
        if entry.model.strip().lower() == normalized:
            return tuple(entry.reasoning_efforts)
    # Catalogue présent mais modèle absent : pas de raisonnement ajustable.
    return ("none",)


def vision_is_supported(provider_set: ProviderSet) -> bool:
    return (
        provider_set.vision.mode == "chat"
        and provider_set.capabilities.vision
    )
