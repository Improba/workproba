"""Client et cache des embeddings pour le ranking mémoire."""

from __future__ import annotations

import hashlib
import logging
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import litellm

from app.embed_batching import iter_embedding_batches

logger = logging.getLogger(__name__)

_CACHE: EmbeddingCache | None = None


@dataclass(frozen=True)
class EmbeddingCacheStats:
    hits: int
    misses: int
    size: int
    max_entries: int

    @property
    def hit_ratio(self) -> float:
        total = self.hits + self.misses
        if total <= 0:
            return 0.0
        return self.hits / total


def _normalize_base_url(base_url: str | None) -> str:
    if not base_url:
        return ""
    parsed = urlparse(base_url.strip())
    if not parsed.scheme or not parsed.netloc:
        return base_url.strip().rstrip("/")
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def content_fingerprint(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def cache_key(model: str, text: str, *, base_url: str | None = None) -> str:
    normalized_base = _normalize_base_url(base_url)
    return f"{model}:{normalized_base}:{content_fingerprint(text)}"


class EmbeddingCache:
    """Cache process-local LRU : clé = modèle + endpoint + empreinte du texte."""

    def __init__(self, max_entries: int) -> None:
        self._max_entries = max(1, max_entries)
        self._entries: OrderedDict[str, tuple[float, ...]] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> tuple[float, ...] | None:
        value = self._entries.get(key)
        if value is None:
            self.misses += 1
            return None
        self._entries.move_to_end(key)
        self.hits += 1
        return value

    def put(self, key: str, vector: tuple[float, ...]) -> None:
        if not vector:
            return
        self._entries[key] = vector
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def stats(self) -> EmbeddingCacheStats:
        return EmbeddingCacheStats(
            hits=self.hits,
            misses=self.misses,
            size=len(self._entries),
            max_entries=self._max_entries,
        )

    def clear(self) -> None:
        self._entries.clear()
        self.hits = 0
        self.misses = 0


def get_embedding_cache() -> EmbeddingCache:
    global _CACHE
    if _CACHE is None:
        from app.config import get_settings

        settings = get_settings()
        _CACHE = EmbeddingCache(settings.memory_embedding_cache_max_entries)
    return _CACHE


def reset_embedding_cache() -> None:
    """Réinitialise le cache (tests ou changement de config)."""
    global _CACHE
    if _CACHE is not None:
        _CACHE.clear()
    _CACHE = None


async def embed_texts(
    texts: list[str],
    *,
    model: str,
    base_url: str | None = None,
    api_key: str | None = None,
    batch_size: int | None = None,
    batch_max_chars: int | None = None,
) -> list[list[float]]:
    if not texts:
        return []

    from app.config import get_settings

    limits = get_settings().limits
    max_items = batch_size if batch_size is not None else limits.embedding_batch_size
    max_chars = batch_max_chars if batch_max_chars is not None else limits.embedding_batch_max_chars

    vectors: list[list[float]] = []
    for batch in iter_embedding_batches(texts, max_items=max_items, max_chars=max_chars):
        kwargs: dict[str, Any] = {
            "model": model,
            "input": batch,
        }
        if base_url:
            kwargs["api_base"] = base_url
        if api_key:
            kwargs["api_key"] = api_key
        response = await litellm.aembedding(**kwargs)
        data = response.data
        if not isinstance(data, list) or len(data) != len(batch):
            raise RuntimeError(
                f"embedding provider returned {len(data) if isinstance(data, list) else 0} "
                f"vectors for {len(batch)} inputs"
            )
        vectors.extend(list(item["embedding"]) for item in data)
    return vectors


async def embed_texts_cached(
    texts: list[str],
    *,
    model: str,
    base_url: str | None = None,
    api_key: str | None = None,
    cache: EmbeddingCache | None = None,
    embed_fn: Any = None,
) -> list[list[float]]:
    """Embed une liste de textes en ne calculant que les entrées absentes du cache."""
    if not texts:
        return []

    active_cache = cache if cache is not None else get_embedding_cache()
    embed = embed_fn or embed_texts

    results: list[list[float] | None] = [None] * len(texts)
    miss_indices: list[int] = []
    miss_texts: list[str] = []
    miss_key_by_text: dict[str, str] = {}

    for index, text in enumerate(texts):
        normalized = text.strip()
        if not normalized:
            raise ValueError("embed_texts_cached received an empty text entry")
        key = cache_key(model, normalized, base_url=base_url)
        hit = active_cache.get(key)
        if hit is not None:
            results[index] = list(hit)
            continue
        if normalized not in miss_key_by_text:
            miss_key_by_text[normalized] = key
            miss_indices.append(index)
            miss_texts.append(normalized)

    if miss_texts:
        fresh_vectors = await embed(
            miss_texts,
            model=model,
            base_url=base_url,
            api_key=api_key,
        )
        vectors_by_text = {
            text: tuple(vector)
            for text, vector in zip(miss_texts, fresh_vectors, strict=True)
        }
        for text, vector in vectors_by_text.items():
            active_cache.put(miss_key_by_text[text], vector)

        for index, text in enumerate(texts):
            if results[index] is not None:
                continue
            vector = vectors_by_text[text.strip()]
            results[index] = list(vector)

    if any(result is None for result in results):
        raise RuntimeError("embedding cache returned incomplete vectors")
    return [list(vector) for vector in results]
