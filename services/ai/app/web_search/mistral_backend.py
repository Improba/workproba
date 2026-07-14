"""Backend Mistral : POST /v1/conversations avec web_search."""

from __future__ import annotations

from typing import Any

import httpx

from app.web_search.errors import WebSearchError

_MISTRAL_CONVERSATIONS_PATH = "/conversations"


async def search_mistral(
    query: str,
    *,
    model: str,
    api_key: str,
    base_url: str,
    premium: bool = False,
    timeout_s: float = 45,
) -> dict[str, Any]:
    tool_type = "web_search_premium" if premium else "web_search"
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        url = f"{root}{_MISTRAL_CONVERSATIONS_PATH}"
    else:
        url = f"{root}/v1{_MISTRAL_CONVERSATIONS_PATH}"

    payload = {
        "model": model,
        "inputs": query,
        "tools": [{"type": tool_type}],
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.post(url, json=payload, headers=headers)
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
