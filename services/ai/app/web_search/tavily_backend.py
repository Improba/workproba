"""Backend Tavily : POST /search (fallback recherche web)."""

from __future__ import annotations

from typing import Any

import httpx

from app.web_search.errors import WebSearchError

_TAVILY_SEARCH_URL = "https://api.tavily.com/search"


def resolve_tavily_api_key(explicit_key: str | None = None) -> str | None:
    if explicit_key and explicit_key.strip():
        return explicit_key.strip()
    from app.config import get_settings

    settings_key = get_settings().tavily_api_key
    if settings_key and settings_key.strip():
        return settings_key.strip()
    return None


def parse_tavily_response(
    payload: dict[str, Any],
    *,
    max_results: int,
) -> dict[str, Any]:
    results_raw = payload.get("results")
    if not isinstance(results_raw, list):
        raise WebSearchError("web_search_bad_response")

    results: list[dict[str, Any]] = []
    citations: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for entry in results_raw:
        if not isinstance(entry, dict):
            continue
        url = str(entry.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        title = str(entry.get("title") or url)
        snippet = str(entry.get("content") or entry.get("snippet") or "").strip()
        source = entry.get("source")
        source_text = str(source).strip() if isinstance(source, str) and source.strip() else None
        item = {
            "title": title,
            "url": url,
            "snippet": snippet,
            "source": source_text,
        }
        results.append(item)
        citations.append({"title": title, "url": url, "source": source_text})
        if len(results) >= max_results:
            break

    answer = str(payload.get("answer") or "").strip()
    return {
        "results": results,
        "citations": citations,
        "summary": answer,
        "usage": {},
    }


async def search_tavily(
    query: str,
    *,
    api_key: str,
    timeout_s: float = 45,
    max_results: int = 8,
) -> dict[str, Any]:
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "include_answer": True,
        "include_raw_content": False,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.post(_TAVILY_SEARCH_URL, json=payload)
    except httpx.TimeoutException as exc:
        raise WebSearchError("web_search_timeout") from exc
    except httpx.HTTPError as exc:
        raise WebSearchError("web_search_unavailable") from exc

    if response.status_code == 429:
        raise WebSearchError("web_search_rate_limit")
    if response.status_code >= 400:
        raise WebSearchError("web_search_unavailable")

    try:
        body = response.json()
    except ValueError as exc:
        raise WebSearchError("web_search_bad_response") from exc

    if not isinstance(body, dict):
        raise WebSearchError("web_search_bad_response")
    return body
