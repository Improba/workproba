"""Unit tests : couche LLM (Pydantic AI models + helpers LiteLLM embeddings)."""

from __future__ import annotations

import pytest
from pydantic import SecretStr
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.llm.config import (
    build_model,
    build_model_settings,
    clamp_reasoning_effort,
    reasoning_effort_for,
    resolve_llm_config,
)
from app.llm.provider_sets import MISTRAL_BUILTIN_SET
from app.llm.provider import parse_tool_arguments, resolve_litellm_model
from app.schemas import LLMProviderConfig


def test_resolve_litellm_model_adds_prefix() -> None:
    assert resolve_litellm_model("mistral", "mistral-embed") == "mistral/mistral-embed"
    assert resolve_litellm_model("ollama", "nomic-embed-text") == "ollama/nomic-embed-text"


def test_resolve_litellm_model_keeps_prefixed() -> None:
    assert resolve_litellm_model("mistral", "mistral/mistral-embed") == "mistral/mistral-embed"


def test_parse_tool_arguments_handles_inputs() -> None:
    assert parse_tool_arguments(None) == {}
    assert parse_tool_arguments({"a": 1}) == {"a": 1}
    assert parse_tool_arguments('{"x": 2}') == {"x": 2}
    assert parse_tool_arguments("not json") == {"raw_arguments": "not json"}
    assert parse_tool_arguments("[1, 2]") == {"value": [1, 2]}


@pytest.mark.parametrize(
    "provider, base_url",
    [
        ("openai_compat", "http://localhost:1234/v1"),
        ("vllm", "http://localhost:8000/v1"),
        ("ollama", None),
        ("mistral", None),
    ],
)
def test_build_model_uses_openai_chat_model(provider: str, base_url: str | None) -> None:
    cfg = LLMProviderConfig(
        provider=provider,  # type: ignore[arg-type]
        model="m",
        base_url=base_url,
        api_key=SecretStr("k") if provider != "ollama" else None,
    )
    model = build_model(cfg)
    assert isinstance(model, OpenAIChatModel)


def test_build_model_mistral_default_base_url() -> None:
    cfg = LLMProviderConfig(provider="mistral", model="mistral-small-latest", api_key=SecretStr("k"))
    model = build_model(cfg)
    assert isinstance(model, OpenAIChatModel)
    # The provider should target the Mistral OpenAI-compat endpoint (normalisé avec slash final).
    provider = model.provider
    assert isinstance(provider, OpenAIProvider)
    assert provider.base_url.rstrip("/") == "https://api.mistral.ai/v1"


def test_build_model_mistral_enables_tags_replay_profile() -> None:
    from app.llm.mistral import MistralChatModel

    cfg = LLMProviderConfig(provider="mistral", model="mistral-small-latest", api_key=SecretStr("k"))
    model = build_model(cfg)
    assert isinstance(model, MistralChatModel)
    # Le replay multi-turn du thinking est activé en mode tags via le profile.
    assert model.profile.get("openai_chat_send_back_thinking_parts") == "tags"


def test_build_model_non_mistral_does_not_set_replay_profile() -> None:
    cfg = LLMProviderConfig(provider="openai", model="gpt-4o", api_key=SecretStr("k"))
    model = build_model(cfg)
    assert model.profile.get("openai_chat_send_back_thinking_parts") != "tags"


def test_build_model_anthropic_constructs_when_dep_present() -> None:
    # anthropic est une dép optionnelle ; si elle est installée, build_model doit
    # construire un AnthropicModel, sinon lever une RuntimeError claire.
    cfg = LLMProviderConfig(provider="anthropic", model="claude-3-5-sonnet-latest", api_key=SecretStr("k"))
    try:
        model = build_model(cfg)
    except RuntimeError as exc:
        assert "anthropic" in str(exc).lower()
    else:
        from pydantic_ai.models.anthropic import AnthropicModel

        assert isinstance(model, AnthropicModel)


def test_build_model_settings_mapping(mistral_config: LLMProviderConfig) -> None:
    settings = build_model_settings(mistral_config)
    assert settings["temperature"] == 0.3
    assert settings["max_tokens"] == 512
    assert settings["extra_headers"] == {"X-Test": "yes"}


def test_build_model_settings_empty_when_unset() -> None:
    settings = build_model_settings(LLMProviderConfig(provider="mistral", model="m"))
    assert settings == {}


def test_build_model_settings_reasoning_effort_mistral_high() -> None:
    cfg = LLMProviderConfig(
        provider="mistral", model="mistral-small-latest", reasoning_effort="high"
    )
    settings = build_model_settings(cfg)
    assert settings["openai_reasoning_effort"] == "high"


def test_build_model_settings_reasoning_effort_mistral_small_clamps_low_to_high() -> None:
    # mistral-small-latest n'accepte que none/high : un effort `low` arrive
    # parfois depuis une session précédente ; le backend doit clamper.
    cfg = LLMProviderConfig(
        provider="mistral", model="mistral-small-latest", reasoning_effort="low"
    )
    settings = build_model_settings(cfg)
    assert settings["openai_reasoning_effort"] == "high"


def test_build_model_settings_reasoning_effort_mistral_small_clamps_medium_to_high() -> None:
    cfg = LLMProviderConfig(
        provider="mistral", model="mistral-small-latest", reasoning_effort="medium"
    )
    settings = build_model_settings(cfg)
    assert settings["openai_reasoning_effort"] == "high"


def test_build_model_settings_reasoning_effort_mistral_medium_clamps_medium_to_high() -> None:
    # mistral-medium-latest n'accepte que none/high (400 sinon).
    cfg = LLMProviderConfig(
        provider="mistral", model="mistral-medium-latest", reasoning_effort="medium"
    )
    settings = build_model_settings(cfg)
    assert settings["openai_reasoning_effort"] == "high"


def test_build_model_settings_reasoning_effort_mistral_medium_clamps_low_to_high() -> None:
    cfg = LLMProviderConfig(
        provider="mistral", model="mistral-medium-latest", reasoning_effort="low"
    )
    settings = build_model_settings(cfg)
    assert settings["openai_reasoning_effort"] == "high"


def test_build_model_settings_reasoning_effort_openai_low() -> None:
    cfg = LLMProviderConfig(provider="openai", model="gpt-4o", reasoning_effort="low")
    settings = build_model_settings(cfg)
    assert settings["openai_reasoning_effort"] == "low"


def test_build_model_settings_reasoning_effort_none_skips_openai_key() -> None:
    cfg = LLMProviderConfig(provider="mistral", model="m", reasoning_effort="none")
    settings = build_model_settings(cfg)
    assert "openai_reasoning_effort" not in settings


def test_build_model_settings_reasoning_effort_anthropic_medium() -> None:
    cfg = LLMProviderConfig(
        provider="anthropic",
        model="claude-3-5-sonnet-latest",
        reasoning_effort="medium",
    )
    settings = build_model_settings(cfg)
    assert settings["thinking"] == "medium"
    assert "openai_reasoning_effort" not in settings


def test_build_model_settings_reasoning_effort_unset_mistral() -> None:
    cfg = LLMProviderConfig(provider="mistral", model="m")
    settings = build_model_settings(cfg)
    assert "openai_reasoning_effort" not in settings


def test_build_model_settings_uses_provider_set_model_efforts() -> None:
    cfg = LLMProviderConfig(
        provider="mistral",
        model="mistral-large-latest",
        reasoning_effort="high",
    )
    settings = build_model_settings(cfg, MISTRAL_BUILTIN_SET)
    assert "openai_reasoning_effort" not in settings

    cfg_small = LLMProviderConfig(
        provider="mistral",
        model="mistral-small-latest",
        reasoning_effort="low",
    )
    settings_small = build_model_settings(cfg_small, MISTRAL_BUILTIN_SET)
    assert settings_small["openai_reasoning_effort"] == "high"


def test_clamp_reasoning_effort_mistral_large_without_provider_set() -> None:
    assert clamp_reasoning_effort("mistral", "mistral-large-latest", "high", None) is None
    assert clamp_reasoning_effort("mistral", "mistral-small-latest", "medium", None) == "high"


def test_reasoning_effort_for() -> None:
    assert reasoning_effort_for(LLMProviderConfig(provider="mistral", model="m")) is None
    assert (
        reasoning_effort_for(
            LLMProviderConfig(provider="mistral", model="m", reasoning_effort="none")
        )
        is None
    )
    assert (
        reasoning_effort_for(
            LLMProviderConfig(provider="mistral", model="m", reasoning_effort="high")
        )
        == "high"
    )


def test_resolve_llm_config_prefers_request_config(mistral_config: LLMProviderConfig) -> None:
    class FakeSettings:
        llm_default_provider = "ollama"
        llm_default_model = "llama3"
        llm_default_base_url = None
        llm_default_api_key = None

    resolved = resolve_llm_config(mistral_config, FakeSettings())
    assert resolved.provider == "mistral"
    assert resolved.model == "mistral-small-latest"


def test_resolve_llm_config_falls_back_to_settings() -> None:
    class FakeSettings:
        llm_default_provider = "ollama"
        llm_default_model = "llama3"
        llm_default_base_url = "http://127.0.0.1:11434/v1"
        llm_default_api_key = None

    resolved = resolve_llm_config(None, FakeSettings())
    assert resolved.provider == "ollama"
    assert resolved.model == "llama3"


def test_resolve_llm_config_from_provider_set() -> None:
    from pydantic import SecretStr

    from app.llm.provider_sets import MISTRAL_BUILTIN_SET

    class FakeSettings:
        llm_default_provider = "ollama"
        llm_default_model = "llama3"
        llm_default_base_url = None
        llm_default_api_key = None

    set_with_key = MISTRAL_BUILTIN_SET.model_copy(deep=True)
    set_with_key.chat = set_with_key.chat.model_copy(update={"api_key": SecretStr("k")})
    resolved = resolve_llm_config(None, FakeSettings(), provider_set=set_with_key)
    assert resolved.provider == "mistral"
    assert resolved.model == "mistral-small-latest"


def test_resolve_embedding_config_prefers_request_config(mistral_config: LLMProviderConfig) -> None:
    from app.main import resolve_embedding_config

    class FakeSettings:
        llm_embedding_provider = "ollama"
        llm_embedding_model = "nomic-embed-text"
        llm_embedding_base_url = "http://127.0.0.1:11434/v1"
        llm_embedding_api_key = None

    embed_cfg = LLMProviderConfig(
        provider="mistral",
        model="mistral-embed",
        base_url="https://api.mistral.ai/v1",
        api_key=SecretStr("k"),
    )
    model, base_url, api_key = resolve_embedding_config(FakeSettings(), embed_cfg)
    assert model == "mistral/mistral-embed"
    assert base_url == "https://api.mistral.ai/v1"
    assert api_key == "k"


def test_resolve_embedding_config_falls_back_to_settings() -> None:
    from app.main import resolve_embedding_config

    class FakeSettings:
        llm_embedding_provider = "ollama"
        llm_embedding_model = "nomic-embed-text"
        llm_embedding_base_url = "http://127.0.0.1:11434/v1"
        llm_embedding_api_key = None

    model, base_url, api_key = resolve_embedding_config(FakeSettings(), None)
    assert model == "ollama/nomic-embed-text"
    assert api_key is None


def test_resolve_embedding_config_returns_none_when_no_model() -> None:
    from app.main import resolve_embedding_config

    class FakeSettings:
        llm_embedding_provider = None
        llm_embedding_model = None
        llm_embedding_base_url = None
        llm_embedding_api_key = None

    model, base_url, api_key = resolve_embedding_config(FakeSettings(), None)
    assert (model, base_url, api_key) == (None, None, None)


def test_resolve_embedding_config_from_provider_set() -> None:
    from app.llm.provider_sets import OLLAMA_BUILTIN_SET
    from app.main import resolve_embedding_config

    class FakeSettings:
        llm_embedding_provider = None
        llm_embedding_model = None
        llm_embedding_base_url = None
        llm_embedding_api_key = None

    model, base_url, api_key = resolve_embedding_config(
        FakeSettings(), None, provider_set=OLLAMA_BUILTIN_SET
    )
    assert model == "ollama/nomic-embed-text"
    assert base_url == "http://127.0.0.1:11434/v1"


def test_agent_turn_request_accepts_embedding_config() -> None:
    from app.schemas import AgentTurnRequest

    embed_cfg = LLMProviderConfig(
        provider="mistral",
        model="mistral-embed",
        api_key=SecretStr("k"),
    )
    req = AgentTurnRequest(
        tenant_id="t",
        project_id="p",
        session_id="s",
        message="hi",
        embedding_config=embed_cfg,
    )
    assert req.embedding_config is not None
    assert req.embedding_config.model == "mistral-embed"
