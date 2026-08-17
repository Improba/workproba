"""Backend Cloud : POST {control_plane}/search/v1 (DeviceBearer)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient
from app.plugins.workproba_cloud.storage import get_control_plane_base_url, is_enrolled
from app.web_search.errors import WebSearchError

_STATUS_TO_DETAIL = {
    429: "web_search_rate_limit",
    504: "web_search_timeout",
}


def cloud_search_ready(cloud_plugin_data_dir: Path | None) -> bool:
    if cloud_plugin_data_dir is None:
        return False
    try:
        return is_enrolled(cloud_plugin_data_dir)
    except OSError:
        return False


def _machine_code(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except (ValueError, TypeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    for key in ("message", "detail", "error"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def map_cloud_search_error(response: httpx.Response) -> WebSearchError:
    code = _machine_code(response)
    if code == "query_empty":
        return WebSearchError("web_search_query_empty")
    if code in {"quota_exceeded", "search_rate_limit"}:
        return WebSearchError("web_search_rate_limit")
    if code in {"mistral_timeout", "search_timeout"}:
        return WebSearchError("web_search_timeout")
    if code in {"search_bad_response", "web_search_bad_response"}:
        return WebSearchError("web_search_bad_response")
    status = response.status_code
    if status == 400:
        return WebSearchError("web_search_unavailable")
    return WebSearchError(_STATUS_TO_DETAIL.get(status, "web_search_unavailable"))


def _is_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _optional_source(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _display_title(value: Any, url: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return url


def _sanitize_search_item(item: Any, *, require_snippet: bool) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    url_raw = item.get("url")
    url = url_raw.strip() if isinstance(url_raw, str) else ""
    if not url or not _is_http_url(url):
        return None
    title = _display_title(item.get("title"), url)
    out: dict[str, Any] = {
        "title": title,
        "url": url,
        "source": _optional_source(item.get("source")),
    }
    if require_snippet:
        snippet = item.get("snippet")
        out["snippet"] = snippet if isinstance(snippet, str) else ""
    return out


def _sanitize_search_items(
    items: list[Any],
    *,
    max_results: int,
    require_snippet: bool,
) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for item in items:
        cleaned = _sanitize_search_item(item, require_snippet=require_snippet)
        if cleaned is None:
            continue
        sanitized.append(cleaned)
        if len(sanitized) >= max_results:
            break
    return sanitized


def _validate_cloud_payload(
    payload: dict[str, Any],
    *,
    query: str,
    max_results: int,
) -> dict[str, Any]:
    results_raw = payload.get("results")
    citations_raw = payload.get("citations")
    if not isinstance(results_raw, list) or not isinstance(citations_raw, list):
        raise WebSearchError("web_search_bad_response")
    results = _sanitize_search_items(
        results_raw,
        max_results=max_results,
        require_snippet=True,
    )
    citations = _sanitize_search_items(
        citations_raw,
        max_results=max_results,
        require_snippet=False,
    )
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    summary = str(payload.get("summary") or "")
    return {
        "query": str(payload.get("query") or query),
        "count": len(results),
        "backend": "cloud",
        "results": results,
        "citations": citations,
        "summary": summary,
        "usage": usage,
    }


async def search_cloud(
    query: str,
    *,
    cloud_plugin_data_dir: Path,
    timeout_s: float,
    max_results: int,
    model: str | None = None,
    premium: bool = False,
) -> dict[str, Any]:
    if not cloud_search_ready(cloud_plugin_data_dir):
        raise WebSearchError("web_search_unavailable")
    base_url = get_control_plane_base_url(cloud_plugin_data_dir)
    if not base_url:
        raise WebSearchError("web_search_unavailable")

    client = CloudControlPlaneClient(
        base_url=base_url,
        plugin_data_dir=cloud_plugin_data_dir,
    )
    try:
        payload = await client.web_search(
            query,
            max_results=max_results,
            model=model,
            premium=premium,
            timeout_s=timeout_s,
        )
    except WebSearchError:
        raise
    except httpx.TimeoutException as exc:
        raise WebSearchError("web_search_timeout") from exc
    except httpx.HTTPError as exc:
        raise WebSearchError("web_search_unavailable") from exc
    except PermissionError as exc:
        raise WebSearchError("web_search_unavailable") from exc
    except ValueError as exc:
        raise WebSearchError("web_search_unavailable") from exc

    if not isinstance(payload, dict):
        raise WebSearchError("web_search_bad_response")
    return _validate_cloud_payload(payload, query=query, max_results=max_results)
