"""Tests backend Cloud POST /search/v1."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from app.limits import DEFAULT_LIMITS
from app.llm.provider_sets import WORKPROBA_CLOUD_BUILTIN_SET
from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient
from app.schemas import ProviderSet, ProviderSetChat
from app.web_search.cloud_backend import map_cloud_search_error, search_cloud
from app.web_search.engine import search_web
from app.web_search.errors import WebSearchError


def _enrolled_cloud_dir(tmp_path: Path) -> Path:
    cloud_dir = tmp_path / "workproba.cloud"
    cloud_dir.mkdir()
    (cloud_dir / "config.json").write_text(
        json.dumps(
            {
                "base_url": "https://cloud.example.test",
                "tokens": {"access_token": "wp_dev_secret", "org_id": "org-a"},
            }
        ),
        encoding="utf-8",
    )
    return cloud_dir


CLOUD_SEARCH_RESPONSE = {
    "query": "Euro 2024 winner",
    "count": 1,
    "backend": "mistral",
    "results": [
        {
            "title": "UEFA Euro Winners List",
            "url": "https://www.example.com/winners.html",
            "snippet": "Spain won.",
            "source": "brave",
        }
    ],
    "citations": [
        {
            "title": "UEFA Euro Winners List",
            "url": "https://www.example.com/winners.html",
            "source": "brave",
        }
    ],
    "summary": "Spain won.",
    "usage": {
        "connector_calls": 1,
        "connector_tokens": 100,
        "estimated_cost_usd": 0.03,
    },
}


def test_map_cloud_search_error_codes() -> None:
    def _resp(status: int, message: str) -> httpx.Response:
        return httpx.Response(
            status,
            json={"message": message},
            request=httpx.Request("POST", "https://cloud.example.test/search/v1"),
        )

    assert str(map_cloud_search_error(_resp(400, "query_empty"))) == "web_search_query_empty"
    assert str(map_cloud_search_error(_resp(400, "unsupported_model"))) == "web_search_unavailable"
    assert str(map_cloud_search_error(_resp(400, "Bad Request"))) == "web_search_unavailable"
    assert str(map_cloud_search_error(_resp(429, "quota_exceeded"))) == "web_search_rate_limit"
    assert str(map_cloud_search_error(_resp(429, "search_rate_limit"))) == "web_search_rate_limit"
    assert str(map_cloud_search_error(_resp(504, "mistral_timeout"))) == "web_search_timeout"
    assert str(map_cloud_search_error(_resp(502, "search_bad_response"))) == "web_search_bad_response"
    assert str(map_cloud_search_error(_resp(403, "not_subscribed"))) == "web_search_unavailable"
    assert str(map_cloud_search_error(_resp(503, "mistral_unavailable"))) == "web_search_unavailable"


@pytest.mark.asyncio
async def test_search_cloud_posts_to_search_v1(tmp_path: Path) -> None:
    cloud_dir = _enrolled_cloud_dir(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/search/v1"
        assert request.headers.get("authorization") == "Bearer wp_dev_secret"
        body = json.loads(request.content.decode("utf-8"))
        assert body["query"] == "Euro 2024 winner"
        assert body["max_results"] == 8
        assert body["model"] == "mistral-medium-latest"
        assert "premium" not in body
        return httpx.Response(200, json=CLOUD_SEARCH_RESPONSE)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://cloud.example.test",
    ) as http_client:
        client = CloudControlPlaneClient(
            base_url="https://cloud.example.test",
            plugin_data_dir=cloud_dir,
            http_client=http_client,
        )
        payload = await client.web_search(
            "Euro 2024 winner",
            max_results=8,
            model="mistral-medium-latest",
        )

    assert payload["count"] == 1
    assert payload["backend"] == "mistral"


@pytest.mark.asyncio
async def test_search_web_device_bearer_uses_cloud_backend(tmp_path: Path) -> None:
    cloud_dir = _enrolled_cloud_dir(tmp_path)
    calls: list[tuple[str, Path | None]] = []

    async def fake_search_cloud(
        query: str,
        *,
        cloud_plugin_data_dir: Path,
        timeout_s: float,
        max_results: int,
        model: str | None = None,
        premium: bool = False,
    ) -> dict:
        _ = (max_results, premium)
        calls.append((query, cloud_plugin_data_dir))
        assert timeout_s == DEFAULT_LIMITS.web_search_timeout_s + 5.0
        assert model == "mistral-medium-latest"
        return {
            "query": query,
            "count": 1,
            "backend": "cloud",
            "results": CLOUD_SEARCH_RESPONSE["results"],
            "citations": CLOUD_SEARCH_RESPONSE["citations"],
            "summary": "Spain won.",
            "usage": CLOUD_SEARCH_RESPONSE["usage"],
        }

    with patch("app.web_search.engine.search_cloud", fake_search_cloud):
        result = await search_web(
            "Euro 2024 winner",
            provider_set=WORKPROBA_CLOUD_BUILTIN_SET,
            locale="fr",
            limits=DEFAULT_LIMITS,
            cloud_plugin_data_dir=cloud_dir,
        )

    assert calls == [("Euro 2024 winner", cloud_dir)]
    assert result["backend"] == "cloud"
    assert result["count"] == 1
    assert result["results"][0]["url"].startswith("https://")


@pytest.mark.asyncio
async def test_search_cloud_unavailable_when_not_enrolled(tmp_path: Path) -> None:
    cloud_dir = tmp_path / "workproba.cloud"
    cloud_dir.mkdir()
    with pytest.raises(WebSearchError) as exc:
        await search_cloud(
            "weather",
            cloud_plugin_data_dir=cloud_dir,
            timeout_s=5,
            max_results=8,
        )
    assert str(exc.value) == "web_search_unavailable"


@pytest.mark.asyncio
async def test_search_web_device_bearer_without_cloud_dir_fails() -> None:
    provider_set = ProviderSet(
        id="workproba-cloud",
        auth_mode="device_bearer",
        chat=ProviderSetChat(provider="mistral", model="mistral-medium-latest"),
    )
    with pytest.raises(WebSearchError) as exc:
        await search_web(
            "weather",
            provider_set=provider_set,
            locale="fr",
            limits=DEFAULT_LIMITS,
            cloud_plugin_data_dir=None,
        )
    assert str(exc.value) == "web_search_unavailable"


@pytest.mark.asyncio
async def test_client_web_search_maps_quota_exceeded(tmp_path: Path) -> None:
    cloud_dir = _enrolled_cloud_dir(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(429, json={"message": "quota_exceeded"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://cloud.example.test",
    ) as http_client:
        client = CloudControlPlaneClient(
            base_url="https://cloud.example.test",
            plugin_data_dir=cloud_dir,
            http_client=http_client,
        )
        with pytest.raises(WebSearchError) as exc:
            await client.web_search("weather", max_results=8)
    assert str(exc.value) == "web_search_rate_limit"


@pytest.mark.asyncio
async def test_search_cloud_rejects_malformed_payload(tmp_path: Path) -> None:
    cloud_dir = _enrolled_cloud_dir(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://cloud.example.test",
    ) as http_client:
        from unittest.mock import patch as _patch

        with _patch(
            "app.web_search.cloud_backend.CloudControlPlaneClient",
            lambda **kwargs: CloudControlPlaneClient(
                **{**kwargs, "http_client": http_client},
            ),
        ):
            with pytest.raises(WebSearchError) as exc:
                await search_cloud(
                    "weather",
                    cloud_plugin_data_dir=cloud_dir,
                    timeout_s=5,
                    max_results=8,
                )
    assert str(exc.value) == "web_search_bad_response"


@pytest.mark.asyncio
async def test_search_cloud_sanitizes_non_http_and_caps_results(tmp_path: Path) -> None:
    cloud_dir = _enrolled_cloud_dir(tmp_path)
    payload = {
        "query": "weather",
        "count": 99,
        "backend": "mistral",
        "results": [
            "skip-me",
            {
                "title": "Bad",
                "url": "javascript:alert(1)",
                "snippet": "nope",
                "source": "brave",
            },
            {
                "title": "One",
                "url": "https://one.example/",
                "snippet": "a",
                "source": "brave",
            },
            {
                "title": "Two",
                "url": "https://two.example/",
                "snippet": "b",
                "source": {"nested": True},
            },
            {
                "title": "Three",
                "url": "https://three.example/",
                "snippet": "c",
                "source": "brave",
            },
        ],
        "citations": [
            {"title": "Bad", "url": "javascript:alert(1)"},
            {"title": "One", "url": "https://one.example/"},
            {"title": "Two", "url": "https://two.example/"},
            {"title": "Three", "url": "https://three.example/"},
        ],
        "summary": "ok",
        "usage": {},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://cloud.example.test",
    ) as http_client:
        with patch(
            "app.web_search.cloud_backend.CloudControlPlaneClient",
            lambda **kwargs: CloudControlPlaneClient(
                **{**kwargs, "http_client": http_client},
            ),
        ):
            result = await search_cloud(
                "weather",
                cloud_plugin_data_dir=cloud_dir,
                timeout_s=5,
                max_results=2,
            )

    assert result["count"] == 2
    assert result["backend"] == "cloud"
    assert [item["url"] for item in result["results"]] == [
        "https://one.example/",
        "https://two.example/",
    ]
    assert result["results"][1]["source"] is None
    assert [item["url"] for item in result["citations"]] == [
        "https://one.example/",
        "https://two.example/",
    ]


@pytest.mark.asyncio
async def test_client_web_search_maps_invalid_json(tmp_path: Path) -> None:
    cloud_dir = _enrolled_cloud_dir(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, text="not-json")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://cloud.example.test",
    ) as http_client:
        client = CloudControlPlaneClient(
            base_url="https://cloud.example.test",
            plugin_data_dir=cloud_dir,
            http_client=http_client,
        )
        with pytest.raises(WebSearchError) as exc:
            await client.web_search("weather", max_results=8)
    assert str(exc.value) == "web_search_bad_response"
