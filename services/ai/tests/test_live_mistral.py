"""Tests live (réseau) contre Mistral.

Désactivés par défaut (besoin d'une clé API + réseau). Activer avec :
    WP_LIVE_LLM=1 pytest tests/test_live_mistral.py -q

La clé et les endpoints sont lus depuis services/ai/.env.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("WP_LIVE_LLM") != "1",
    reason="Live Mistral tests désactivés (définir WP_LIVE_LLM=1).",
)

_LIVE_KEY = os.getenv("LLM_DEFAULT_API_KEY") or "xlplBQAxZCjIOYeAoBg4ozGJD55RyR1p"
_LIVE_BASE = os.getenv("LLM_DEFAULT_BASE_URL") or "https://api.mistral.ai/v1"


async def test_live_chat_streaming_incremental() -> None:
    from pydantic_ai import Agent
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    model = OpenAIChatModel(
        model_name="mistral-small-latest",
        provider=OpenAIProvider(base_url=_LIVE_BASE, api_key=_LIVE_KEY),
    )
    agent = Agent(model=model, output_type=str, system_prompt="Réponds très court.")

    deltas: list[str] = []
    async with agent.iter(user_prompt="Dis bonjour en exactement 3 mots.", deps=None) as run:
        async for node in run:
            if Agent.is_model_request_node(node):
                async with node.stream(run.ctx) as stream:
                    async for delta in stream.stream_text(delta=True, debounce_by=None):
                        deltas.append(delta)
        final = run.result.output if run.result else ""

    assert deltas, "Le stream doit produire des deltas"
    # Les deltas ne doivent pas contenir le texte accumulé complet (incrémental).
    assert all(d != final for d in deltas[:-1])
    assert "".join(deltas).strip() == final.strip()


async def test_live_rag_embeddings(tmp_path: Path) -> None:
    from app.rag.store import RagStore

    store = RagStore(
        db_path=tmp_path / "memory.db",
        embedding_model="mistral/mistral-embed",
        embedding_base_url=_LIVE_BASE,
        embedding_api_key=_LIVE_KEY,
    )
    await store.index_document(
        document_id="rapport.md",
        title="rapport",
        mime_type="text/markdown",
        text="Le CA Q2 atteint 12345 EUR, hausse de 12%. Notes: prioriser le support client.",
    )
    await store.index_document(
        document_id="notes.md",
        title="notes",
        mime_type="text/markdown",
        text="Le support client est la priorite Q3.",
    )
    results = await store.search(query="support client", limit=2)
    store.close()

    assert len(results) == 2
    # Le document le plus pertinent sémantiquement doit arriver en tête.
    assert results[0]["document_id"] == "notes.md"
