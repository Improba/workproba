from __future__ import annotations

import re


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
