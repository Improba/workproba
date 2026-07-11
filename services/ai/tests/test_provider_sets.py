"""Tests provider sets : schéma, résolution, capabilities, endpoint test."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import SecretStr

from app.llm.config import resolve_llm_config
from app.llm.provider_sets import (
    MISTRAL_BUILTIN_SET,
    OLLAMA_BUILTIN_SET,
    BUILTIN_PROVIDER_SETS,
    ocr_is_supported,
    resolve_chat_from_set,
    resolve_embeddings_from_set,
    resolve_vision_mode,
    set_capabilities,
    vision_is_supported,
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
    assert parsed.is_default is True


def test_builtin_sets_mistral_is_default() -> None:
    assert len(BUILTIN_PROVIDER_SETS) == 2
    assert MISTRAL_BUILTIN_SET.is_default
    assert not OLLAMA_BUILTIN_SET.is_default
    assert MISTRAL_BUILTIN_SET.is_builtin
    assert OLLAMA_BUILTIN_SET.is_builtin


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
    cfg = resolve_chat_from_set(MISTRAL_BUILTIN_SET)
    assert cfg.reasoning_effort is None


def test_resolve_embeddings_from_set() -> None:
    cfg = resolve_embeddings_from_set(MISTRAL_BUILTIN_SET)
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


def test_capabilities_and_vision_helpers() -> None:
    caps = set_capabilities(MISTRAL_BUILTIN_SET)
    assert caps.vision is True
    assert caps.tools is True
    assert resolve_vision_mode(MISTRAL_BUILTIN_SET) == "chat"
    assert ocr_is_supported(MISTRAL_BUILTIN_SET)
    assert vision_is_supported(MISTRAL_BUILTIN_SET)


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
