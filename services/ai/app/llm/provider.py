"""Couche LLM du sidecar.

Le chat/agent passe désormais par les modèles natifs de Pydantic AI
(`app.llm.config.build_model`). LiteLLM est conservé uniquement pour les
embeddings RAG (`app.rag.store`), d'où le maintien de `resolve_litellm_model`.
"""

import json
from typing import Any

import litellm

# Coupe le bruit/telemetry de LiteLLM côté sidecar desktop (embeddings RAG).
litellm.set_verbose = False
litellm.suppress_debug_messages = True

# Map entre le provider métier et le préfixe modèle attendu par LiteLLM
# (embeddings). Si `model` contient déjà un préfixe (ex. "ollama/nomic-embed"),
# on le garde tel quel.
_PROVIDER_PREFIX: dict[str, str] = {
    "openai_compat": "openai",
    "openai": "openai",
    "mistral": "mistral",
    "ollama": "ollama",
    "vllm": "hosted_vllm",
    "anthropic": "anthropic",
}


def resolve_litellm_model(provider: str, model: str) -> str:
    if "/" in model:
        return model
    prefix = _PROVIDER_PREFIX.get(provider, "openai")
    return f"{prefix}/{model}"


def parse_tool_arguments(raw_arguments: str | dict[str, Any] | None) -> dict[str, Any]:
    """Convertit les arguments d'un tool call (str JSON ou dict) en dict."""
    if raw_arguments is None:
        return {}
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if not raw_arguments:
        return {}
    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError:
        return {"raw_arguments": raw_arguments}
    return parsed if isinstance(parsed, dict) else {"value": parsed}
