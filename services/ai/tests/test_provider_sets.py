"""Tests provider sets : schéma, résolution, capabilities, endpoint test."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from pydantic import SecretStr

from app.llm.config import resolve_llm_config
from app.llm.provider_sets import (
    MISTRAL_BUILTIN_SET,
    OLLAMA_BUILTIN_SET,
    OLLAMA_DEFAULT_BASE_URL,
    WORKPROBA_CLOUD_BUILTIN_SET,
    BUILTIN_PROVIDER_SETS,
    CloudNotEnrolledError,
    MissingApiKeyError,
    ocr_is_supported,
    resolve_chat_from_set,
    resolve_embeddings_from_set,
    resolve_vision_mode,
    set_capabilities,
    supported_reasoning_efforts_for_set,
    vision_is_supported,
    web_search_is_supported,
)
from app.main import resolve_embedding_config
from app.schemas import (
    AgentTurnRequest,
    ProviderSet,
    ProviderSetCapabilities,
    ProviderSetChat,
    ProviderSetEmbeddings,
    ProviderSetOcr,
    ProviderSetVision,
)


def test_provider_set_ocr_normalizes_mistral_ocr_alias() -> None:
    ocr = ProviderSetOcr(provider="mistral_ocr", mode="auto")
    assert ocr.provider == "mistral"


def test_provider_set_schema_roundtrip() -> None:
    raw = MISTRAL_BUILTIN_SET.model_dump()
    parsed = ProviderSet.model_validate(raw)
    assert parsed.id == "mistral-default"
    assert parsed.chat.provider == "mistral"
    assert parsed.embeddings is not None
    assert parsed.is_default is False
    assert parsed.auth_mode == "api_key"


def test_builtin_sets_workproba_cloud_is_default() -> None:
    assert len(BUILTIN_PROVIDER_SETS) == 3
    assert WORKPROBA_CLOUD_BUILTIN_SET.is_default
    assert WORKPROBA_CLOUD_BUILTIN_SET.auth_mode == "device_bearer"
    assert WORKPROBA_CLOUD_BUILTIN_SET.ui_mode_locked is True
    assert not MISTRAL_BUILTIN_SET.is_default
    assert not OLLAMA_BUILTIN_SET.is_default
    assert MISTRAL_BUILTIN_SET.is_builtin
    assert OLLAMA_BUILTIN_SET.is_builtin
    dumped = WORKPROBA_CLOUD_BUILTIN_SET.model_dump()
    assert "access_token" not in str(dumped).lower()
    assert WORKPROBA_CLOUD_BUILTIN_SET.chat.api_key is None
    assert WORKPROBA_CLOUD_BUILTIN_SET.chat.api_key_ref is None


def test_resolve_chat_from_set_maps_reasoning() -> None:
    base = MISTRAL_BUILTIN_SET.model_copy(deep=True)
    base.chat = base.chat.model_copy(update={"reasoning": "high", "api_key": SecretStr("k")})
    cfg = resolve_chat_from_set(base)
    assert cfg.provider == "mistral"
    assert cfg.model == "mistral-small-latest"
    assert cfg.reasoning_effort == "high"
    assert cfg.api_key is not None
    assert cfg.api_key.get_secret_value() == "k"


def test_resolve_chat_auto_reasoning_is_none() -> None:
    base = MISTRAL_BUILTIN_SET.model_copy(deep=True)
    base.chat = base.chat.model_copy(update={"api_key": SecretStr("k")})
    cfg = resolve_chat_from_set(base)
    assert cfg.reasoning_effort is None


def test_resolve_chat_raises_when_cloud_key_missing() -> None:
    with pytest.raises(MissingApiKeyError):
        resolve_chat_from_set(MISTRAL_BUILTIN_SET)


def test_resolve_workproba_cloud_without_token_raises_not_enrolled() -> None:
    with pytest.raises(CloudNotEnrolledError):
        resolve_chat_from_set(WORKPROBA_CLOUD_BUILTIN_SET)


def test_resolve_workproba_cloud_injects_device_token(tmp_path) -> None:
    cloud_dir = tmp_path / "workproba.cloud"
    cloud_dir.mkdir()
    config = {
        "base_url": "https://cloud.example.com",
        "tokens": {"access_token": "device-token-xyz"},
    }
    (cloud_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")

    cfg = resolve_chat_from_set(
        WORKPROBA_CLOUD_BUILTIN_SET,
        cloud_plugin_data_dir=cloud_dir,
    )
    assert cfg.api_key is not None
    assert cfg.api_key.get_secret_value() == "device-token-xyz"
    assert cfg.base_url == "https://cloud.example.com/llm/v1"
    assert cfg.provider == "mistral"

    embed = resolve_embeddings_from_set(
        WORKPROBA_CLOUD_BUILTIN_SET,
        cloud_plugin_data_dir=cloud_dir,
    )
    assert embed is not None
    assert embed.provider == "openai_compat"
    assert embed.api_key is not None
    assert embed.api_key.get_secret_value() == "device-token-xyz"
    assert embed.base_url == "https://cloud.example.com/llm/v1"


def test_resolve_workproba_cloud_token_without_base_url_raises(tmp_path) -> None:
    """DeviceBearer ne doit jamais tomber sur un endpoint public."""
    cloud_dir = tmp_path / "workproba.cloud"
    cloud_dir.mkdir()
    config = {"tokens": {"access_token": "device-token-xyz"}}
    (cloud_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(CloudNotEnrolledError):
        resolve_chat_from_set(
            WORKPROBA_CLOUD_BUILTIN_SET,
            cloud_plugin_data_dir=cloud_dir,
        )


def test_resolve_workproba_cloud_serialized_builtin_has_no_token() -> None:
    payload = WORKPROBA_CLOUD_BUILTIN_SET.model_dump(mode="json")
    serialized = json.dumps(payload)
    assert "device-token" not in serialized
    assert "access_token" not in serialized


def test_resolve_embeddings_raises_when_cloud_key_missing() -> None:
    with pytest.raises(MissingApiKeyError):
        resolve_embeddings_from_set(MISTRAL_BUILTIN_SET)


def test_resolve_embeddings_from_set() -> None:
    base = MISTRAL_BUILTIN_SET.model_copy(deep=True)
    base.chat = base.chat.model_copy(update={"api_key": SecretStr("k")})
    base.embeddings = base.embeddings.model_copy(update={"api_key": SecretStr("k")}) if base.embeddings else None
    cfg = resolve_embeddings_from_set(base)
    assert cfg is not None
    assert cfg.model == "mistral-embed"
    assert cfg.provider == "mistral"


def test_resolve_embeddings_none_when_absent() -> None:
    minimal = ProviderSet(
        id="x",
        name="X",
        chat=ProviderSetChat(provider="ollama", model="m"),
        embeddings=None,
    )
    assert resolve_embeddings_from_set(minimal) is None


def test_builtin_mistral_chat_models_catalog() -> None:
    assert MISTRAL_BUILTIN_SET.chat is not None
    models = MISTRAL_BUILTIN_SET.chat.models
    assert models is not None
    assert [m.model for m in models] == [
        "mistral-small-latest",
        "mistral-medium-latest",
        "mistral-large-latest",
    ]
    small = next(m for m in models if m.model == "mistral-small-latest")
    medium = next(m for m in models if m.model == "mistral-medium-latest")
    large = next(m for m in models if m.model == "mistral-large-latest")
    assert small.reasoning_efforts == ["none", "high"]
    assert large.reasoning_efforts == ["none"]
    assert small.context_window == 256000
    assert small.hint == "Hybride : chat, code et raisonnement à la demande. Rapide et économique."
    assert medium.hint == "Modèle frontier pour agents, code long et workflows multi-étapes."
    assert large.hint == "Flagship multilingue et multimodal. Qualité maximale."


def test_provider_set_from_front_sidecar_fixture() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "mistral_builtin_sidecar.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    parsed = ProviderSet.model_validate(data)
    assert parsed.id == "mistral-default"
    assert parsed.chat is not None
    assert parsed.chat.provider == "mistral"
    models = parsed.chat.models
    assert models is not None
    assert [m.model for m in models] == [
        "mistral-small-latest",
        "mistral-medium-latest",
        "mistral-large-latest",
    ]
    small = next(m for m in models if m.model == "mistral-small-latest")
    medium = next(m for m in models if m.model == "mistral-medium-latest")
    large = next(m for m in models if m.model == "mistral-large-latest")
    assert small.hint == "Hybride : chat, code et raisonnement à la demande. Rapide et économique."
    assert medium.hint == "Modèle frontier pour agents, code long et workflows multi-étapes."
    assert large.hint == "Flagship multilingue et multimodal. Qualité maximale."
    assert small.reasoning_efforts == ["none", "high"]
    assert medium.reasoning_efforts == ["none", "high"]
    assert large.reasoning_efforts == ["none"]
    assert small.context_window == 256000
    assert parsed.capabilities.web_search is True


def test_supported_reasoning_efforts_for_set() -> None:
    efforts = supported_reasoning_efforts_for_set(
        MISTRAL_BUILTIN_SET,
        "mistral-medium-latest",
    )
    assert efforts == ("none", "high")
    assert supported_reasoning_efforts_for_set(
        MISTRAL_BUILTIN_SET,
        "mistral-large-latest",
    ) == ("none",)
    assert supported_reasoning_efforts_for_set(OLLAMA_BUILTIN_SET, "llama3.2") is None
    assert supported_reasoning_efforts_for_set(
        MISTRAL_BUILTIN_SET,
        "unknown-model",
    ) == ("none",)


def test_capabilities_and_vision_helpers() -> None:
    caps = set_capabilities(MISTRAL_BUILTIN_SET)
    assert caps.vision is True
    assert caps.tools is True
    assert caps.web_search is True
    assert resolve_vision_mode(MISTRAL_BUILTIN_SET) == "chat"
    assert ocr_is_supported(MISTRAL_BUILTIN_SET)
    assert vision_is_supported(MISTRAL_BUILTIN_SET)


def test_ollama_builtin_web_search_capability() -> None:
    caps = set_capabilities(OLLAMA_BUILTIN_SET)
    assert caps.web_search is True
    assert web_search_is_supported(OLLAMA_BUILTIN_SET)


def test_ollama_builtin_vision_not_supported() -> None:
    assert not vision_is_supported(OLLAMA_BUILTIN_SET)


def test_ollama_builtin_ocr_not_implemented() -> None:
    assert not ocr_is_supported(OLLAMA_BUILTIN_SET)


def test_resolve_llm_config_prefers_provider_set(mistral_config) -> None:
    class FakeSettings:
        llm_default_provider = "ollama"
        llm_default_model = "llama3"
        llm_default_base_url = None
        llm_default_api_key = None

    resolved = resolve_llm_config(
        mistral_config,
        FakeSettings(),
        provider_set=OLLAMA_BUILTIN_SET,
    )
    assert resolved.provider == "ollama"
    assert resolved.model == "llama3.2"


def test_resolve_embedding_config_prefers_provider_set() -> None:
    class FakeSettings:
        llm_embedding_provider = "ollama"
        llm_embedding_model = "nomic-embed-text"
        llm_embedding_base_url = "http://127.0.0.1:11434/v1"
        llm_embedding_api_key = None

    set_with_key = MISTRAL_BUILTIN_SET.model_copy(deep=True)
    assert set_with_key.embeddings is not None
    set_with_key.embeddings = set_with_key.embeddings.model_copy(
        update={"api_key": SecretStr("embed-key")}
    )
    model, base_url, api_key = resolve_embedding_config(
        FakeSettings(),
        None,
        provider_set=set_with_key,
    )
    assert model == "mistral/mistral-embed"
    assert api_key == "embed-key"


def test_agent_turn_request_accepts_provider_set() -> None:
    req = AgentTurnRequest(
        project_id="p",
        session_id="s",
        message="hi",
        provider_set=MISTRAL_BUILTIN_SET,
    )
    assert req.provider_set is not None
    assert req.provider_set.id == "mistral-default"


@pytest.mark.asyncio
async def test_llm_sets_test_endpoint_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    import app.auth as authmod
    import app.main as mainmod

    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)

    payload = MISTRAL_BUILTIN_SET.model_copy(deep=True)
    payload.chat = payload.chat.model_copy(update={"api_key": SecretStr("k")})
    if payload.embeddings is not None:
        payload.embeddings = payload.embeddings.model_copy(
            update={"api_key": SecretStr("k")}
        )

    fake_ok = mainmod.LlmTestResult(ok=True, detail="OK", model_count=2)
    with patch.object(mainmod, "llm_test", new=AsyncMock(return_value=fake_ok)):
        with TestClient(mainmod.app) as client:
            resp = client.post(
                "/llm/sets/test",
                json=payload.model_dump(mode="json"),
                headers={"X-Internal-Secret": "desktop-dev-secret"},
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["chat"]["ok"] is True
    assert data["embeddings"]["ok"] is True
    assert data["ocr"]["supported"] is True
    assert data["vision"]["supported"] is True
    assert "secret" not in resp.text.lower()
    assert "embed-key" not in resp.text


def test_minimal_provider_set_without_ocr() -> None:
    minimal = ProviderSet(
        id="chat-only",
        name="Chat seul",
        chat=ProviderSetChat(provider="ollama", model="llama3"),
        ocr=ProviderSetOcr(provider="docling", mode="none"),
        vision=ProviderSetVision(mode="none"),
        capabilities=ProviderSetCapabilities(reasoning="low", vision=False, tools=True),
    )
    assert not ocr_is_supported(minimal)
    assert not vision_is_supported(minimal)


def test_enrollment_resolve_quota_error_then_switch_set(tmp_path) -> None:
    """Parcours : cloud enrollé → resolve → quota_exceeded → switch mistral/ollama."""
    from openai import RateLimitError

    from app.llm.cloud_errors import parse_cloud_llm_error_code
    from app.llm.fallback import is_fallbackable

    cloud_dir = tmp_path / "workproba.cloud"
    cloud_dir.mkdir()
    config = {
        "base_url": "https://cloud.example.com",
        "tokens": {"access_token": "device-token-xyz"},
    }
    (cloud_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")

    cloud_cfg = resolve_chat_from_set(
        WORKPROBA_CLOUD_BUILTIN_SET,
        cloud_plugin_data_dir=cloud_dir,
    )
    assert cloud_cfg.provider == "mistral"
    assert cloud_cfg.api_key is not None
    assert cloud_cfg.api_key.get_secret_value() == "device-token-xyz"
    assert cloud_cfg.base_url == "https://cloud.example.com/llm/v1"

    quota_exc = RateLimitError(
        "quota_exceeded",
        response=httpx.Response(
            429,
            request=httpx.Request("POST", f"{cloud_cfg.base_url}/chat/completions"),
            json={"statusCode": 429, "message": "quota_exceeded"},
        ),
        body={"message": "quota_exceeded"},
    )
    assert parse_cloud_llm_error_code(quota_exc) == "quota_exceeded"
    assert is_fallbackable(quota_exc) == (False, "")

    mistral = MISTRAL_BUILTIN_SET.model_copy(deep=True)
    mistral.chat = mistral.chat.model_copy(update={"api_key": SecretStr("mistral-key")})
    mistral_cfg = resolve_chat_from_set(mistral)
    assert mistral_cfg.provider == "mistral"
    assert mistral_cfg.api_key is not None
    assert mistral_cfg.api_key.get_secret_value() == "mistral-key"
    assert mistral_cfg.base_url == MISTRAL_BUILTIN_SET.chat.base_url

    ollama_cfg = resolve_chat_from_set(OLLAMA_BUILTIN_SET)
    assert ollama_cfg.provider == "ollama"
    assert ollama_cfg.base_url == OLLAMA_DEFAULT_BASE_URL
    assert ollama_cfg.api_key is None
