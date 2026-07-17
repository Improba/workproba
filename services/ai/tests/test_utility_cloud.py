"""Utility LLM : résolution device_bearer via provider_set (pas d'API publique)."""

from __future__ import annotations

import json

import pytest

from app.llm.provider_sets import WORKPROBA_CLOUD_BUILTIN_SET, CloudNotEnrolledError
from app.llm.utility import resolve_utility_config
from app.schemas import LLMProviderConfig


class _Settings:
    llm_utility_provider = None
    llm_utility_model = None
    llm_utility_base_url = None
    llm_utility_api_key = None


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


def test_resolve_utility_cloud_without_dir_raises() -> None:
    with pytest.raises(CloudNotEnrolledError):
        resolve_utility_config(
            None,
            None,
            _Settings(),
            provider_set=WORKPROBA_CLOUD_BUILTIN_SET,
            cloud_plugin_data_dir=None,
        )
