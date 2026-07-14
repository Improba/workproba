"""Tests embeddings pour ranking mémoire."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import asyncio

import pytest

from app.agent.embedding_cache import embed_texts
from app.agent.memory_embeddings import (
    MemoryRankingContext,
    collect_tagged_memories,
    prepare_memory_ranking_context,
    prepare_ranking_for_turn,
    resolve_embedding_credentials,
)
from app.memory_stores import open_memory_store_for_scope
from app.schemas import LLMProviderConfig, ProviderSet, ProviderSetChat, ProviderSetEmbeddings


@pytest.mark.asyncio
async def test_embed_texts_uses_litellm(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_aembedding(**kwargs: Any) -> Any:
        texts = kwargs["input"]
        return type(
            "Resp",
            (),
            {
                "data": [
                    {"embedding": [float(index), 0.0]}
                    for index, _text in enumerate(texts)
                ]
            },
        )()

    monkeypatch.setattr("app.agent.embedding_cache.litellm.aembedding", fake_aembedding)
    vectors = await embed_texts(["alpha", "beta"], model="test/embed")
    assert vectors == [[0.0, 0.0], [1.0, 0.0]]


def test_resolve_embedding_credentials_from_provider_set() -> None:
    provider_set = ProviderSet(
        id="test",
        embeddings=ProviderSetEmbeddings(
            provider="ollama",
            model="nomic-embed-text",
            base_url="http://127.0.0.1:11434/v1",
        ),
    )
    from app.config import get_settings

    model, base_url, api_key = resolve_embedding_credentials(
        get_settings(),
        None,
        provider_set=provider_set,
    )
    assert model == "ollama/nomic-embed-text"
    assert base_url == "http://127.0.0.1:11434/v1"
    assert api_key is None


def test_collect_tagged_memories_merges_scopes(tmp_path: Path) -> None:
    app_data = tmp_path / "app_data"
    workspace = app_data / "spaces" / "space-1" / ".workproba"
    workspace.mkdir(parents=True)
    user_store = open_memory_store_for_scope("user", workspace)
    project_store = open_memory_store_for_scope("project", workspace)
    try:
        user_store.add_memory(content="Préfère le français", source="user")
        project_store.add_memory(content="Client ACME", source="agent")
    finally:
        user_store.close()
        project_store.close()

    tagged = collect_tagged_memories(workspace)
    scopes = {item["_scope"] for item in tagged}
    assert scopes == {"user", "project"}


@pytest.mark.asyncio
async def test_prepare_memory_ranking_context_builds_maps(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    project_store = open_memory_store_for_scope("project", workspace)
    try:
        created = project_store.add_memory(content="Budget RH 2026", source="agent")
        memory_id = str(created["id"])
    finally:
        project_store.close()

    async def fake_embed(texts: list[str], **kwargs: Any) -> list[list[float]]:
        _ = kwargs
        return [[float(index), 0.1] for index, _text in enumerate(texts)]

    monkeypatch.setattr(
        "app.agent.embedding_cache.embed_texts",
        fake_embed,
    )

    context = await prepare_memory_ranking_context(
        query="budget RH",
        workspace_data_dir=workspace,
        sessions=[{"id": "sess-1", "title": "Budget", "summary": "Discussion RH"}],
        embedding_model="test/embed",
    )
    assert isinstance(context, MemoryRankingContext)
    assert context.query_embedding is not None
    assert memory_id in context.memory_embeddings
    assert "sess-1" in context.session_embeddings


@pytest.mark.asyncio
async def test_prepare_memory_ranking_context_times_out(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import Settings

    settings = Settings(memory_ranking_embedding_timeout_s=0.01)
    monkeypatch.setattr("app.agent.memory_embeddings.get_settings", lambda: settings)

    async def slow_embed(*args: Any, **kwargs: Any) -> list[list[float]]:
        _ = (args, kwargs)
        await asyncio.sleep(0.2)
        return [[1.0, 0.0]]

    monkeypatch.setattr("app.agent.embedding_cache.embed_texts", slow_embed)

    workspace = tmp_path / "ws"
    workspace.mkdir()
    result = await prepare_memory_ranking_context(
        query="budget",
        workspace_data_dir=workspace,
        sessions=[],
        embedding_model="test/embed",
    )
    assert result is None


@pytest.mark.asyncio
async def test_prepare_ranking_for_turn_disabled_by_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import Settings

    settings = Settings(memory_ranking_semantic_enabled=False)
    monkeypatch.setattr("app.agent.memory_embeddings.get_settings", lambda: settings)

    result = await prepare_ranking_for_turn(
        query="hello",
        workspace_data_dir=tmp_path,
        sessions=[],
        embedding_config=LLMProviderConfig(provider="ollama", model="nomic-embed-text"),
        provider_set=None,
    )
    assert result is None
