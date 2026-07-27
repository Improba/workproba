"""Utility LLM : résolution device_bearer via provider_set (pas d'API publique)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.llm.provider_sets import WORKPROBA_CLOUD_BUILTIN_SET, CloudNotEnrolledError
from app.llm.utility import generate_title, resolve_utility_config
from app.schemas import LLMProviderConfig, UtilityTitleRequest


class _Settings:
    llm_utility_provider = None
    llm_utility_model = None
    llm_utility_base_url = None
    llm_utility_api_key = None


class _FakeUsage:
    input_tokens = 1
    output_tokens = 1
    total_tokens = 2


class _FakeRunResult:
    def __init__(self, output: str) -> None:
        self.output = output
        self.usage = _FakeUsage()


class _FakeUtilityAgent:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    async def run(self, _prompt: str) -> _FakeRunResult:
        return _FakeRunResult('"Salutation"')


def test_resolve_utility_prefers_provider_set_over_flat_mistral(tmp_path) -> None:
    cloud_dir = tmp_path / "workproba.cloud"
    cloud_dir.mkdir()
    (cloud_dir / "config.json").write_text(
        json.dumps(
            {
                "base_url": "https://cloud.example.com",
                "tokens": {"access_token": "device-token-xyz"},
            }
        ),
        encoding="utf-8",
    )

    flat = LLMProviderConfig(provider="mistral", model="mistral-small-latest")
    cfg = resolve_utility_config(
        flat,
        flat,
        _Settings(),
        provider_set=WORKPROBA_CLOUD_BUILTIN_SET,
        cloud_plugin_data_dir=cloud_dir,
    )
    assert cfg.base_url == "https://cloud.example.com/llm/v1"
    assert cfg.api_key is not None
    assert cfg.api_key.get_secret_value() == "device-token-xyz"
    assert cfg.provider == "mistral"
    assert cfg.model == "mistral-small-latest"
    assert cfg.reasoning_effort is None


def test_resolve_utility_cloud_without_dir_raises() -> None:
    with pytest.raises(CloudNotEnrolledError):
        resolve_utility_config(
            None,
            None,
            _Settings(),
            provider_set=WORKPROBA_CLOUD_BUILTIN_SET,
            cloud_plugin_data_dir=None,
        )


@pytest.mark.asyncio
async def test_generate_title_uses_catalogue_small_without_reasoning(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cloud_dir = tmp_path / "workproba.cloud"
    cloud_dir.mkdir()
    (cloud_dir / "config.json").write_text(
        json.dumps(
            {
                "base_url": "https://cloud.example.com",
                "tokens": {"access_token": "device-token-xyz"},
            }
        ),
        encoding="utf-8",
    )

    captured: dict[str, Any] = {}

    def _capture_model(config: LLMProviderConfig) -> object:
        captured["config"] = config
        return object()

    monkeypatch.setattr("app.llm.utility.Agent", _FakeUtilityAgent)
    monkeypatch.setattr("app.llm.utility.build_model", _capture_model)
    monkeypatch.setattr("app.llm.utility.build_model_settings", lambda _config: {})

    # Set chat default is medium + high ; utility must still pick small + none.
    assert WORKPROBA_CLOUD_BUILTIN_SET.chat.model == "mistral-medium-latest"
    assert WORKPROBA_CLOUD_BUILTIN_SET.chat.reasoning == "high"

    result = await generate_title(
        UtilityTitleRequest(
            first_user_message="salut toi",
            provider_set=WORKPROBA_CLOUD_BUILTIN_SET,
            cloud_plugin_data_dir=str(cloud_dir),
            locale="fr",
        ),
        _Settings(),
    )

    assert result.title == "Salutation"
    cfg = captured["config"]
    assert cfg.model == "mistral-small-latest"
    assert cfg.reasoning_effort is None
    assert cfg.base_url == "https://cloud.example.com/llm/v1"
