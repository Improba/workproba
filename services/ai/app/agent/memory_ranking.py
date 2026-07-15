from __future__ import annotations

import math
import re


def cosine_similarity(left: list[float] | tuple[float, ...], right: list[float] | tuple[float, ...]) -> float:
    """Similarité cosinus entre deux vecteurs (0 si l'un est nul)."""
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm_left = math.sqrt(sum(a * a for a in left))
    norm_right = math.sqrt(sum(b * b for b in right))
    if norm_left <= 0.0 or norm_right <= 0.0:
        return 0.0
    return dot / (norm_left * norm_right)


def _memory_item_key(item: dict) -> str:
    return str(item.get("id") or item.get("content") or "")


def _normalize_content(content: str) -> str:
    return re.sub(r"\s+", " ", content.strip().lower())


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"\w+", text.lower()) if token}


def dedupe_memories_keep_order(items: list[dict]) -> list[dict]:
    """Déduplique par contenu normalisé en conservant le premier exemplaire."""
    seen: set[str] = set()
    result: list[dict] = []
    for item in items:
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        key = _normalize_content(content)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def rank_sessions_by_query(
    sessions: list[dict],
    query: str,
    k: int,
    *,
    min_overlap: int = 2,
) -> list[dict]:
    """Classe les sessions par recouvrement lexical titre + résumé avec la requête."""
    if k <= 0 or not sessions:
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    required_overlap = min(min_overlap, len(query_tokens))

    scored: list[tuple[int, int, dict]] = []
    for index, session in enumerate(sessions):
        haystack = f"{session.get('title') or ''} {session.get('summary') or ''}"
        overlap = len(query_tokens & _tokenize(haystack))
        if overlap < required_overlap:
            continue
        scored.append((overlap, index, session))

    scored.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
    return [session for _, _, session in scored[:k]]


def rank_memories_by_query(items: list[dict], query: str, k: int) -> list[dict]:
    """Classe les souvenirs par recouvrement lexical avec la requête.

    `items` est supposé en ordre chronologique (index 0 = plus ancien).
    En cas d'égalité de score, on préfère les entrées les plus récentes.
    Sans recouvrement lexical, ne retourne rien (le recent_floor couvre le reste).
    """
    if k <= 0 or not items:
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return items[-k:]

    scored: list[tuple[int, int, dict]] = []
    for index, item in enumerate(items):
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        content_tokens = _tokenize(content)
        overlap = len(query_tokens & content_tokens)
        if overlap <= 0:
            continue
        scored.append((overlap, index, item))

    if not scored:
        return []

    scored.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
    return [item for _, _, item in scored[:k]]


def _sort_ranked(
    scored: list[tuple[float, int, dict]],
    *,
    recent_at_low_index: bool,
) -> None:
    """Trie par score décroissant ; tie-break vers l'entrée la plus récente."""
    if recent_at_low_index:
        scored.sort(key=lambda entry: (-entry[0], entry[1]))
    else:
        scored.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)


def _hybrid_scores(
    *,
    query: str,
    texts: list[tuple[int, dict, str]],
    query_embedding: tuple[float, ...] | None,
    item_embeddings: dict[str, tuple[float, ...]] | None,
    semantic_weight: float,
    min_semantic_score: float,
    recent_at_low_index: bool,
) -> list[tuple[float, int, dict]]:
    """Score hybride lexical + sémantique pour une liste (index, item, texte)."""
    query_tokens = _tokenize(query)
    if not query_tokens and query_embedding is None:
        return []

    lexical_scores: list[tuple[int, int, dict, float]] = []
    for index, item, text in texts:
        overlap = len(query_tokens & _tokenize(text)) if query_tokens else 0
        if overlap <= 0 and query_embedding is None:
            continue
        lexical_scores.append((overlap, index, item, float(overlap)))

    if not lexical_scores:
        return []

    max_lexical = max(score for score, _, _, _ in lexical_scores) or 1.0
    scored: list[tuple[float, int, dict]] = []

    for overlap, index, item, lexical_norm in lexical_scores:
        lexical_component = lexical_norm / max_lexical
        semantic_component = 0.0
        if query_embedding is not None:
            key = _memory_item_key(item) if "content" in item else str(item.get("id") or "")
            vector = item_embeddings.get(key) if item_embeddings else None
            if vector is not None:
                semantic_component = cosine_similarity(query_embedding, vector)
                if semantic_component < min_semantic_score and overlap <= 0:
                    continue
            elif overlap <= 0:
                continue
        elif overlap <= 0:
            continue
        hybrid = (
            semantic_weight * semantic_component
            + (1.0 - semantic_weight) * lexical_component
        )
        scored.append((hybrid, index, item))

    _sort_ranked(scored, recent_at_low_index=recent_at_low_index)
    return scored


def rank_memories_hybrid(
    items: list[dict],
    query: str,
    k: int,
    *,
    query_embedding: tuple[float, ...] | None = None,
    item_embeddings: dict[str, tuple[float, ...]] | None = None,
    semantic_weight: float = 0.6,
    min_semantic_score: float = 0.25,
) -> list[dict]:
    """Classe les souvenirs par score hybride (sémantique + lexical).

    Sans embeddings, retombe sur le ranking lexical existant.
    """
    if query_embedding is None and item_embeddings is None:
        return rank_memories_by_query(items, query, k)

    if k <= 0 or not items:
        return []

    texts = [
        (index, item, str(item.get("content") or "").strip())
        for index, item in enumerate(items)
        if str(item.get("content") or "").strip()
    ]
    scored = _hybrid_scores(
        query=query,
        texts=texts,
        query_embedding=query_embedding,
        item_embeddings=item_embeddings,
        semantic_weight=semantic_weight,
        min_semantic_score=min_semantic_score,
        recent_at_low_index=False,
    )
    if not scored:
        return rank_memories_by_query(items, query, k)
    return [item for _, _, item in scored[:k]]


def rank_sessions_hybrid(
    sessions: list[dict],
    query: str,
    k: int,
    *,
    query_embedding: tuple[float, ...] | None = None,
    session_embeddings: dict[str, tuple[float, ...]] | None = None,
    semantic_weight: float = 0.6,
    min_semantic_score: float = 0.25,
    min_overlap: int = 2,
) -> list[dict]:
    """Classe les sessions par score hybride (sémantique + lexical)."""
    if query_embedding is None and session_embeddings is None:
        return rank_sessions_by_query(
            sessions,
            query,
            k,
            min_overlap=min_overlap,
        )

    if k <= 0 or not sessions:
        return []

    texts = [
        (index, session, f"{session.get('title') or ''} {session.get('summary') or ''}")
        for index, session in enumerate(sessions)
    ]
    scored = _hybrid_scores(
        query=query,
        texts=texts,
        query_embedding=query_embedding,
        item_embeddings=session_embeddings,
        semantic_weight=semantic_weight,
        min_semantic_score=min_semantic_score,
        recent_at_low_index=True,
    )
    if not scored:
        return rank_sessions_by_query(
            sessions,
            query,
            k,
            min_overlap=min_overlap,
        )
    return [session for _, _, session in scored[:k]]
