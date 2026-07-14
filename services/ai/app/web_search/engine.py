"""Moteur de recherche web délégué (backends pluggables)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypedDict

from app.limits import Limits
from app.schemas import ProviderSet
from app.web_search import config
from app.web_search.backends import register_web_search_backend, run_registered_backend
from app.web_search.errors import WebSearchError
from app.web_search.mistral_backend import search_mistral

SearchBackend = Callable[..., Awaitable[dict[str, Any]]]

_engine_factory: SearchBackend | None = None


async def _mistral_registered_backend(
    query: str,
    *,
    provider_set: ProviderSet | None,
    locale: str,
    limits: Limits,
    premium: bool = False,
) -> dict[str, Any]:
    _ = locale
    if provider_set is None or provider_set.chat is None:
        raise WebSearchError("web_search_unavailable")

    from app.llm.provider_sets import MissingApiKeyError, resolve_chat_from_set

    try:
        llm_config = resolve_chat_from_set(provider_set)
    except (MissingApiKeyError, ValueError) as exc:
        raise WebSearchError("web_search_unavailable") from exc

    api_key = llm_config.api_key.get_secret_value() if llm_config.api_key else None
    if not api_key:
        raise WebSearchError("web_search_unavailable")

    return await search_mistral(
        query,
        model=llm_config.model,
        api_key=api_key,
        base_url=llm_config.base_url or "https://api.mistral.ai/v1",
        premium=premium,
        timeout_s=limits.web_search_timeout_s,
    )


register_web_search_backend("mistral", _mistral_registered_backend)


class WebCitation(TypedDict):
    title: str
    url: str
    source: str | None


class WebResult(TypedDict):
    title: str
    url: str
    snippet: str
    source: str | None


def normalize_query(query: str, *, max_chars: int) -> str:
    text = query.strip()
    if not text:
        raise WebSearchError("web_search_query_empty")
    if len(text) > max_chars:
        text = text[:max_chars]
    return text


def parse_mistral_conversation_response(
    payload: dict[str, Any],
    *,
    max_results: int,
    premium: bool = False,
) -> dict[str, Any]:
    """Transforme une réponse Conversations Mistral en résultat outil normalisé."""
    outputs = payload.get("outputs")
    if not isinstance(outputs, list):
        raise WebSearchError("web_search_bad_response")

    citations: list[WebCitation] = []
    text_parts: list[str] = []
    seen_urls: set[str] = set()

    for entry in outputs:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "message.output":
            continue
        content = entry.get("content")
        if not isinstance(content, list):
            continue
        for chunk in content:
            if not isinstance(chunk, dict):
                continue
            chunk_type = chunk.get("type")
            if chunk_type == "text":
                text = str(chunk.get("text") or "").strip()
                if text:
                    text_parts.append(text)
            elif chunk_type == "tool_reference":
                url = str(chunk.get("url") or "").strip()
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                citations.append(
                    {
                        "title": str(chunk.get("title") or url),
                        "url": url,
                        "source": chunk.get("source"),
                    }
                )

    summary_snippet = " ".join(text_parts).strip()
    results: list[WebResult] = []
    for citation in citations[:max_results]:
        results.append(
            {
                "title": citation["title"],
                "url": citation["url"],
                "snippet": summary_snippet[:500] if summary_snippet else "",
                "source": citation.get("source"),
            }
        )

    usage_raw = payload.get("usage")
    usage: dict[str, Any] = {}
    connector_calls = 0
    connector_tokens = 0
    if isinstance(usage_raw, dict):
        connector_tokens = int(usage_raw.get("connector_tokens") or 0)
        connectors = usage_raw.get("connectors")
        if isinstance(connectors, dict):
            connector_calls = int(
                connectors.get("web_search") or connectors.get("web_search_premium") or 0
            )
        if connector_calls <= 0 and citations:
            connector_calls = 1
        cost_per_call = (
            config.MISTRAL_WEB_SEARCH_PREMIUM_COST_USD
            if premium
            else config.MISTRAL_WEB_SEARCH_COST_USD
        )
        usage = {
            "connector_calls": connector_calls,
            "connector_tokens": connector_tokens,
            "estimated_cost_usd": round(connector_calls * cost_per_call, 6),
        }

    return {
        "results": results,
        "citations": citations[:max_results],
        "usage": usage,
        "summary": summary_snippet,
    }


def set_search_backend(factory: SearchBackend | None) -> None:
    global _engine_factory
    _engine_factory = factory


async def search_web(
    query: str,
    *,
    provider_set: ProviderSet | None,
    locale: str,
    limits: Limits,
    premium: bool = False,
) -> dict[str, Any]:
    """Exécute une recherche web via le backend adapté au provider set."""
    _ = locale
    normalized = normalize_query(query, max_chars=limits.web_search_query_max_chars)

    if _engine_factory is not None:
        payload = await _engine_factory(
            normalized,
            provider_set=provider_set,
            locale=locale,
            limits=limits,
            premium=premium,
        )
        if isinstance(payload, dict) and "query" in payload:
            return payload
        parsed = parse_mistral_conversation_response(
            payload if isinstance(payload, dict) else {},
            max_results=limits.web_search_max_results,
            premium=premium,
        )
        return _finalize(normalized, parsed, backend="mock")

    if provider_set is None or provider_set.chat is None:
        raise WebSearchError("web_search_unavailable")

    chat = provider_set.chat
    registered = chat.provider
    if not registered:
        raise WebSearchError("web_search_unavailable")

    try:
        raw = await run_registered_backend(
            registered,
            normalized,
            provider_set=provider_set,
            locale=locale,
            limits=limits,
            premium=premium,
        )
    except KeyError:
        raise WebSearchError("web_search_unavailable") from None
    except WebSearchError:
        raise
    except Exception as exc:
        raise WebSearchError("web_search_unavailable") from exc

    if isinstance(raw, dict) and "query" in raw and "results" in raw:
        return raw

    parsed = parse_mistral_conversation_response(
        raw,
        max_results=limits.web_search_max_results,
        premium=premium,
    )
    return _finalize(normalized, parsed, backend=registered)


def _finalize(query: str, parsed: dict[str, Any], *, backend: str) -> dict[str, Any]:
    results = parsed.get("results")
    citations = parsed.get("citations")
    result_list = results if isinstance(results, list) else []
    citation_list = citations if isinstance(citations, list) else []
    usage = parsed.get("usage") if isinstance(parsed.get("usage"), dict) else {}
    summary = str(parsed.get("summary") or "")
    return {
        "query": query,
        "count": len(result_list),
        "backend": backend,
        "results": result_list,
        "citations": citation_list,
        "summary": summary,
        "usage": usage,
    }
