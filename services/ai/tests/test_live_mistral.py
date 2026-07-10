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


async def test_live_mistral_reasoning_effort_thinking_events() -> None:
    from pydantic import SecretStr

    from app.agent.loop import AgentLoop
    from app.agent.tools import build_agent
    from app.llm.config import build_model, build_model_settings
    from app.schemas import (
        AgentTurnRequest,
        LLMProviderConfig,
        ThinkingDeltaEvent,
        ThinkingStartEvent,
        TokenEvent,
    )
    from app.sandbox.runner import SandboxRunner
    from conftest import FakeProjectClient

    api_key = os.getenv("MISTRAL_API_KEY") or os.getenv("LLM_DEFAULT_API_KEY")
    if not api_key:
        pytest.skip("MISTRAL_API_KEY ou LLM_DEFAULT_API_KEY requis pour le test live.")

    llm_config = LLMProviderConfig(
        provider="mistral",
        model="mistral-small-latest",
        api_key=SecretStr(api_key),
        reasoning_effort="high",
    )
    agent = build_agent(build_model(llm_config))
    loop = AgentLoop(
        agent=agent,
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30),
        max_iterations=3,
        model_settings=build_model_settings(llm_config),
    )
    request = AgentTurnRequest(
        tenant_id="t",
        project_id="p",
        session_id="s-live-reasoning",
        message="What is 17 * 23?",
        llm_provider_config=llm_config,
    )

    events = [event async for event in loop.run_turn(request)]
    types = [type(e).__name__ for e in events]

    assert ThinkingStartEvent.__name__ in types
    assert ThinkingDeltaEvent.__name__ in types
    assert TokenEvent.__name__ in types
    assert types.index(ThinkingStartEvent.__name__) < types.index(TokenEvent.__name__)


async def test_live_mistral_reasoning_multiturn_replay() -> None:
    """Valide que le thinking du tour 1 est renvoyé au tour 2 sans casser l'API Mistral.

    Le profile MistralChatModel active `openai_chat_send_back_thinking_parts='tags'` :
    le ThinkingPart du tour 1 est sérialisé en balises <think>...</think> dans le
    message assistant renvoyé. Ce test vérifie qu'un second tour avec cet historique
    se termine avec succès (réponse reçue, aucune erreur).
    """
    from pydantic import SecretStr

    from app.agent.loop import AgentLoop
    from app.agent.tools import build_agent
    from app.llm.config import build_model, build_model_settings
    from app.schemas import (
        AgentTurnRequest,
        ChatMessage,
        DoneEvent,
        ErrorEvent,
        LLMProviderConfig,
        ThinkingDeltaEvent,
        TokenEvent,
    )
    from app.sandbox.runner import SandboxRunner
    from conftest import FakeProjectClient

    api_key = os.getenv("MISTRAL_API_KEY") or os.getenv("LLM_DEFAULT_API_KEY")
    if not api_key:
        pytest.skip("MISTRAL_API_KEY ou LLM_DEFAULT_API_KEY requis pour le test live.")

    def make_loop() -> AgentLoop:
        llm_config = LLMProviderConfig(
            provider="mistral",
            model="mistral-small-latest",
            api_key=SecretStr(api_key),
            reasoning_effort="high",
        )
        agent = build_agent(build_model(llm_config))
        return AgentLoop(
            agent=agent,
            project_client=FakeProjectClient(),
            sandbox_runner=SandboxRunner(timeout_seconds=30),
            max_iterations=3,
            model_settings=build_model_settings(llm_config),
        )

    common = {
        "tenant_id": "t",
        "project_id": "p",
        "session_id": "s-live-reasoning-multiturn",
        "llm_provider_config": LLMProviderConfig(
            provider="mistral",
            model="mistral-small-latest",
            api_key=SecretStr(api_key),
            reasoning_effort="high",
        ),
    }

    # Tour 1 : on récupère le thinking + la réponse.
    loop1 = make_loop()
    turn1 = [event async for event in loop1.run_turn(
        AgentTurnRequest(**common, message="What is 17 * 23?")
    )]
    thinking_text = "".join(
        e.content for e in turn1 if isinstance(e, ThinkingDeltaEvent)
    )
    answer_text = "".join(e.content for e in turn1 if isinstance(e, TokenEvent))
    assert thinking_text, "Le tour 1 doit produire une trace de raisonnement."
    assert answer_text, "Le tour 1 doit produire une réponse."

    # Tour 2 : on renvoie l'historique contenant le thinking du tour 1.
    history = [
        ChatMessage(role="user", content="What is 17 * 23?"),
        ChatMessage(role="assistant", content=answer_text, thinking=thinking_text),
    ]
    loop2 = make_loop()
    turn2 = [event async for event in loop2.run_turn(
        AgentTurnRequest(**common, message="Now multiply that by 3.", history=history)
    )]

    assert not any(isinstance(e, ErrorEvent) for e in turn2), (
        "Le tour 2 ne doit pas lever d'erreur : le replay du thinking est accepté par Mistral."
    )
    # Le tour 2 doit produire une réponse textuelle (le replay n'a pas cassé le stream).
    assert any(isinstance(e, TokenEvent) for e in turn2)
    assert any(isinstance(e, DoneEvent) for e in turn2)
