"""Embeddings pour le ranking sémantique de la mémoire explicite et des sessions."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from app.agent.embedding_cache import (
    EmbeddingCacheStats,
    embed_texts,
    embed_texts_cached,
    get_embedding_cache,
)
from app.config import Settings, get_settings
from app.llm.provider import resolve_litellm_model
from app.llm.provider_sets import resolve_embeddings_from_set
from app.memory_stores import open_memory_store_for_scope
from app.schemas import LLMProviderConfig, ProviderSet

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MemoryRankingContext:
    """Vecteurs pré-calculés pour un tour agent (ranking hybride)."""

    query_embedding: tuple[float, ...] | None
    memory_embeddings: dict[str, tuple[float, ...]]
    session_embeddings: dict[str, tuple[float, ...]]
    cache_stats: EmbeddingCacheStats | None = None


def resolve_embedding_credentials(
    settings: Settings,
    embedding_config: LLMProviderConfig | None,
    *,
    provider_set: ProviderSet | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Résout modèle / base_url / api_key pour les embeddings d'un tour."""
    if provider_set is not None:
        set_embed = resolve_embeddings_from_set(provider_set)
        if set_embed is not None and set_embed.model:
            model = set_embed.model
            if "/" not in model and set_embed.provider:
                model = resolve_litellm_model(set_embed.provider, model)
            api_key = (
                set_embed.api_key.get_secret_value()
                if set_embed.api_key
                else None
            )
            return model, set_embed.base_url, api_key

    if embedding_config is not None and embedding_config.model:
        model = embedding_config.model
        if "/" not in model and embedding_config.provider:
            model = resolve_litellm_model(embedding_config.provider, model)
        api_key = (
            embedding_config.api_key.get_secret_value()
            if embedding_config.api_key
            else None
        )
        return model, embedding_config.base_url, api_key

    if not settings.llm_embedding_model:
        return None, None, None

    model = settings.llm_embedding_model
    if "/" not in model and settings.llm_embedding_provider:
        model = resolve_litellm_model(settings.llm_embedding_provider, model)
    return model, settings.llm_embedding_base_url, settings.llm_embedding_api_key


def collect_tagged_memories(workspace_data_dir: Any) -> list[dict]:
    """Charge les souvenirs user + project avec tag de scope."""
    from app.agent.memory_ranking import dedupe_memories_keep_order

    def _collect(scope: str) -> list[dict]:
        try:
            store = open_memory_store_for_scope(scope, workspace_data_dir)
        except Exception:
            return []
        try:
            return [
                {**item, "_scope": scope}
                for item in store.list_memories()
            ]
        finally:
            store.close()

    return dedupe_memories_keep_order(_collect("user") + _collect("project"))


def _session_text(session: dict) -> str:
    return f"{session.get('title') or ''} {session.get('summary') or ''}".strip()


def _to_tuple_map(
    keys: list[str],
    vectors: list[list[float]],
) -> dict[str, tuple[float, ...]]:
    return {
        key: tuple(vector)
        for key, vector in zip(keys, vectors, strict=True)
        if key and vector
    }


async def prepare_memory_ranking_context(
    *,
    query: str,
    workspace_data_dir: Any,
    sessions: list[dict],
    embedding_model: str,
    embedding_base_url: str | None = None,
    embedding_api_key: str | None = None,
    memories: list[dict] | None = None,
) -> MemoryRankingContext | None:
    """Pré-calcule les embeddings pour le ranking hybride d'un tour."""
    normalized_query = query.strip()
    if not normalized_query or not embedding_model:
        return None

    if memories is None:
        memories = collect_tagged_memories(workspace_data_dir)

    memory_texts: list[str] = []
    memory_keys: list[str] = []
    for item in memories:
        content = str(item.get("content") or "").strip()
        item_id = str(item.get("id") or content)
        if not content:
            continue
        memory_keys.append(item_id)
        memory_texts.append(content)

    session_keys: list[str] = []
    session_texts: list[str] = []
    for session in sessions:
        text = _session_text(session)
        session_id = str(session.get("id") or "")
        if not text or not session_id:
            continue
        session_keys.append(session_id)
        session_texts.append(text)

    texts = [normalized_query, *memory_texts, *session_texts]
    if len(texts) <= 1 and not memory_texts and not session_texts:
        return None

    cache = get_embedding_cache()
    cache_hits_before = cache.hits
    cache_misses_before = cache.misses

    try:
        settings = get_settings()
        vectors = await asyncio.wait_for(
            embed_texts_cached(
                texts,
                model=embedding_model,
                base_url=embedding_base_url,
                api_key=embedding_api_key,
                cache=cache,
            ),
            timeout=settings.memory_ranking_embedding_timeout_s,
        )
    except TimeoutError:
        logger.warning("memory ranking embeddings timed out")
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory ranking embeddings failed: %s", exc)
        return None

    if not vectors or len(vectors) != len(texts):
        return None

    cache_stats = EmbeddingCacheStats(
        hits=cache.hits - cache_hits_before,
        misses=cache.misses - cache_misses_before,
        size=cache.stats().size,
        max_entries=cache.stats().max_entries,
    )
    if cache_stats.hits > 0:
        logger.debug(
            "memory ranking embedding cache turn hits=%s misses=%s ratio=%.2f",
            cache_stats.hits,
            cache_stats.misses,
            cache_stats.hit_ratio,
        )

    query_embedding = tuple(vectors[0])
    offset = 1
    memory_vectors = vectors[offset : offset + len(memory_texts)]
    offset += len(memory_texts)
    session_vectors = vectors[offset : offset + len(session_texts)]

    return MemoryRankingContext(
        query_embedding=query_embedding,
        memory_embeddings=_to_tuple_map(memory_keys, memory_vectors),
        session_embeddings=_to_tuple_map(session_keys, session_vectors),
        cache_stats=cache_stats,
    )


async def prepare_ranking_for_turn(
    *,
    query: str,
    workspace_data_dir: Any | None,
    sessions: list[dict],
    embedding_config: LLMProviderConfig | None,
    provider_set: ProviderSet | None,
    memories: list[dict] | None = None,
) -> MemoryRankingContext | None:
    """Point d'entrée : respecte le flag settings et résout les credentials."""
    settings = get_settings()
    if not settings.memory_ranking_semantic_enabled or workspace_data_dir is None:
        return None

    model, base_url, api_key = resolve_embedding_credentials(
        settings,
        embedding_config,
        provider_set=provider_set,
    )
    if not model:
        return None

    return await prepare_memory_ranking_context(
        query=query,
        workspace_data_dir=workspace_data_dir,
        sessions=sessions,
        embedding_model=model,
        embedding_base_url=base_url,
        embedding_api_key=api_key,
        memories=memories,
    )
