"""Provider sets : résolution chat/embeddings/vision depuis un set unifié."""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr

from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD
from app.plugins.workproba_cloud.storage import (
    get_access_token,
    get_control_plane_base_url,
)
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
WORKPROBA_CLOUD_BUILTIN_SET_ID = "workproba-cloud"

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
    is_default=False,
    is_builtin=True,
)

WORKPROBA_CLOUD_BUILTIN_SET = ProviderSet(
    id=WORKPROBA_CLOUD_BUILTIN_SET_ID,
    name="Improba Cloud",
    description="Cloud Improba géré. Chat, vision, OCR et embeddings via votre compte.",
    badges=["Cloud Improba", "Recommandé"],
    auth_mode="device_bearer",
    chat=ProviderSetChat(
        # mistral : active MistralChatModel (thinking chunks) tout en passant
        # par le proxy OpenAI-compat cloud (`base_url` résolu à {cp}/llm/v1).
        provider="mistral",
        model="mistral-small-latest",
        reasoning="auto",
        models=list(MISTRAL_CHAT_MODELS),
    ),
    embeddings=ProviderSetEmbeddings(
        # openai_compat : LiteLLM route via api_base custom vers le proxy cloud.
        provider="openai_compat",
        model="mistral-embed",
    ),
    ocr=ProviderSetOcr(provider="mistral", mode="auto"),
    vision=ProviderSetVision(mode="chat"),
    capabilities=ProviderSetCapabilities(
        reasoning="medium",
        vision=True,
        tools=True,
        # Le proxy /llm/v1 n'expose pas l'API Agents / web search Mistral.
        web_search=False,
    ),
    is_default=True,
    is_builtin=True,
    ui_mode_locked=True,
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

BUILTIN_PROVIDER_SETS: tuple[ProviderSet, ...] = (
    WORKPROBA_CLOUD_BUILTIN_SET,
    MISTRAL_BUILTIN_SET,
    OLLAMA_BUILTIN_SET,
)

_LOCAL_PROVIDERS = frozenset({"ollama", "vllm"})


class MissingApiKeyError(ValueError):
    """Clé API cloud absente du provider set."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(
            f"Clé API manquante pour le provider {provider}. "
            "Renseignez-la dans Réglages → Modèles IA."
        )


class CloudNotEnrolledError(ValueError):
    """Appareil non connecté au cloud Improba (DeviceBearer absent)."""

    def __init__(self) -> None:
        super().__init__(
            "Appareil non connecté au cloud Improba. "
            "Connectez-vous depuis Projets → Cloud."
        )


def provider_requires_api_key(provider: str) -> bool:
    return provider not in _LOCAL_PROVIDERS


def resolve_cloud_plugin_data_dir(
    *,
    cloud_plugin_data_dir: Path | str | None = None,
    plugin_data_dir: Path | str | None = None,
) -> Path | None:
    if cloud_plugin_data_dir:
        return Path(cloud_plugin_data_dir).expanduser().resolve()
    if plugin_data_dir:
        return (
            Path(plugin_data_dir).expanduser().resolve().parent / PLUGIN_WORKPROBA_CLOUD
        )
    return None


def build_cloud_llm_base_url(control_plane_base_url: str) -> str:
    return f"{control_plane_base_url.rstrip('/')}/llm/v1"


def _resolve_base_url(
    block: ProviderSetChat | ProviderSetEmbeddings,
    *,
    provider_set: ProviderSet,
    cloud_plugin_data_dir: Path | None,
) -> str | None:
    if provider_set.auth_mode == "device_bearer":
        # Jamais de fallback vers un provider public : le DeviceBearer
        # ne doit pas quitter le plan de contrôle.
        if cloud_plugin_data_dir is None:
            raise CloudNotEnrolledError()
        control_plane = get_control_plane_base_url(cloud_plugin_data_dir)
        if not control_plane:
            raise CloudNotEnrolledError()
        return build_cloud_llm_base_url(control_plane)
    if block.base_url:
        return block.base_url.rstrip("/")
    return block.base_url


def _chat_reasoning_to_effort(reasoning: str) -> ReasoningEffort | None:
    if reasoning == "auto":
        return None
    if reasoning in ("none", "low", "medium", "high"):
        return reasoning  # type: ignore[return-value]
    return None


def _resolve_device_bearer_token(cloud_plugin_data_dir: Path | None) -> SecretStr:
    if cloud_plugin_data_dir is None:
        raise CloudNotEnrolledError()
    token = get_access_token(cloud_plugin_data_dir)
    if not token:
        raise CloudNotEnrolledError()
    return SecretStr(token)


def _resolve_api_key(
    chat_or_embed: ProviderSetChat | ProviderSetEmbeddings,
    *,
    provider_set: ProviderSet,
    cloud_plugin_data_dir: Path | None = None,
    fallback_key: SecretStr | None = None,
) -> SecretStr | None:
    if provider_set.auth_mode == "device_bearer":
        return _resolve_device_bearer_token(cloud_plugin_data_dir)
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


def resolve_chat_from_set(
    provider_set: ProviderSet,
    *,
    cloud_plugin_data_dir: Path | str | None = None,
    plugin_data_dir: Path | str | None = None,
) -> LLMProviderConfig:
    """Construit une config LLM chat depuis le sous-bloc chat du set."""
    chat = provider_set.chat
    if chat is None:
        raise ValueError("Provider set sans configuration chat")
    cloud_dir = resolve_cloud_plugin_data_dir(
        cloud_plugin_data_dir=cloud_plugin_data_dir,
        plugin_data_dir=plugin_data_dir,
    )
    return LLMProviderConfig(
        provider=chat.provider,
        model=chat.model,
        base_url=_resolve_base_url(
            chat,
            provider_set=provider_set,
            cloud_plugin_data_dir=cloud_dir,
        ),
        api_key=_resolve_api_key(
            chat,
            provider_set=provider_set,
            cloud_plugin_data_dir=cloud_dir,
        ),
        reasoning_effort=_chat_reasoning_to_effort(chat.reasoning),
    )


def resolve_fallback_chat_config(
    provider_set: ProviderSet,
    *,
    cloud_plugin_data_dir: Path | str | None = None,
    plugin_data_dir: Path | str | None = None,
) -> LLMProviderConfig | None:
    """Construit la config chat de repli, ou None si absente ou non utilisable."""
    chat_fallback = provider_set.chat_fallback
    if chat_fallback is None:
        return None
    cloud_dir = resolve_cloud_plugin_data_dir(
        cloud_plugin_data_dir=cloud_plugin_data_dir,
        plugin_data_dir=plugin_data_dir,
    )
    chat_key = provider_set.chat.api_key if provider_set.chat else None
    try:
        api_key = _resolve_api_key(
            chat_fallback,
            provider_set=provider_set,
            cloud_plugin_data_dir=cloud_dir,
            fallback_key=chat_key,
        )
    except (MissingApiKeyError, CloudNotEnrolledError):
        return None
    return LLMProviderConfig(
        provider=chat_fallback.provider,
        model=chat_fallback.model,
        base_url=_resolve_base_url(
            chat_fallback,
            provider_set=provider_set,
            cloud_plugin_data_dir=cloud_dir,
        ),
        api_key=api_key,
        reasoning_effort=_chat_reasoning_to_effort(chat_fallback.reasoning),
    )


def resolve_embeddings_from_set(
    provider_set: ProviderSet,
    *,
    cloud_plugin_data_dir: Path | str | None = None,
    plugin_data_dir: Path | str | None = None,
) -> LLMProviderConfig | None:
    """Construit une config embeddings depuis le set, ou None si absent."""
    if provider_set.embeddings is None:
        return None
    embed = provider_set.embeddings
    cloud_dir = resolve_cloud_plugin_data_dir(
        cloud_plugin_data_dir=cloud_plugin_data_dir,
        plugin_data_dir=plugin_data_dir,
    )
    chat_key = provider_set.chat.api_key if provider_set.chat else None
    return LLMProviderConfig(
        provider=embed.provider,
        model=embed.model,
        base_url=_resolve_base_url(
            embed,
            provider_set=provider_set,
            cloud_plugin_data_dir=cloud_dir,
        ),
        api_key=_resolve_api_key(
            embed,
            provider_set=provider_set,
            cloud_plugin_data_dir=cloud_dir,
            fallback_key=chat_key,
        ),
    )


def resolve_vision_mode(provider_set: ProviderSet) -> str:
    """Mode vision effectif du set (``chat`` ou ``none``)."""
    return provider_set.vision.mode


def set_capabilities(provider_set: ProviderSet) -> ProviderSetCapabilities:
    """Capacités effectives du set (reasoning, vision, tools, web_search)."""
    caps = provider_set.capabilities.model_copy()
    if caps.web_search:
        return caps
    # Proxy cloud : ne pas activer la recherche web native Mistral
    # (API Agents absente du plan de contrôle V1).
    if provider_set.auth_mode == "device_bearer":
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
