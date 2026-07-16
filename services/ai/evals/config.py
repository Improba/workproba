"""Environment configuration for live eval runs."""

from __future__ import annotations

import os

DEFAULT_BASE_URL = "https://api.mistral.ai/v1"
DEFAULT_EMBEDDING_MODEL = "mistral/mistral-embed"
DEFAULT_JUDGE_MODEL = "mistral-small-latest"


def eval_enabled() -> bool:
    return os.getenv("WP_EVAL") == "1"


def get_api_key() -> str | None:
    return os.getenv("MISTRAL_API_KEY") or os.getenv("LLM_DEFAULT_API_KEY")


def get_base_url() -> str:
    return os.getenv("LLM_DEFAULT_BASE_URL", DEFAULT_BASE_URL)
