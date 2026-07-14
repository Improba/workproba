"""Tests parsing réponses Mistral web_search."""

from __future__ import annotations

import pytest

from app.web_search.engine import (
    normalize_query,
    parse_mistral_conversation_response,
)
from app.web_search.errors import WebSearchError
from fixtures.mistral_web_search_response import MISTRAL_WEB_SEARCH_RESPONSE


def test_parse_mistral_conversation_response_extracts_citations() -> None:
    parsed = parse_mistral_conversation_response(MISTRAL_WEB_SEARCH_RESPONSE, max_results=8)
    citations = parsed["citations"]
    assert len(citations) == 2
    assert citations[0]["url"] == "https://www.example.com/winners.html"
    assert citations[0]["title"] == "UEFA Euro Winners List"
    assert citations[0]["source"] == "brave"
    assert parsed["results"][0]["url"] == citations[0]["url"]
    assert "Spain" in parsed["summary"]
    assert parsed["usage"]["connector_calls"] == 1
    assert parsed["usage"]["estimated_cost_usd"] == pytest.approx(0.03)


def test_parse_mistral_conversation_response_deduplicates_urls() -> None:
    payload = {
        "outputs": [
            {
                "type": "message.output",
                "content": [
                    {
                        "type": "tool_reference",
                        "title": "A",
                        "url": "https://dup.example/a",
                        "source": "brave",
                    },
                    {
                        "type": "tool_reference",
                        "title": "B",
                        "url": "https://dup.example/a",
                        "source": "brave",
                    },
                ],
            }
        ],
        "usage": {"connectors": {"web_search": 1}},
    }
    parsed = parse_mistral_conversation_response(payload, max_results=8)
    assert len(parsed["citations"]) == 1


def test_parse_mistral_conversation_response_empty_outputs() -> None:
    parsed = parse_mistral_conversation_response({"outputs": []}, max_results=8)
    assert parsed["results"] == []
    assert parsed["citations"] == []


def test_parse_mistral_conversation_response_rejects_invalid_outputs() -> None:
    with pytest.raises(WebSearchError) as exc:
        parse_mistral_conversation_response({"outputs": "bad"}, max_results=8)
    assert str(exc.value) == "web_search_bad_response"


def test_normalize_query_rejects_empty() -> None:
    with pytest.raises(WebSearchError):
        normalize_query("   ", max_chars=500)


def test_normalize_query_truncates() -> None:
    text = normalize_query("x" * 600, max_chars=500)
    assert len(text) == 500
