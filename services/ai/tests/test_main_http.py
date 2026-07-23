"""Test HTTP bout-en-bout de /agent/turn via TestClient + TestModel."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.models.test import TestModel

import app.auth as authmod
import app.llm.utility as utilitymod
import app.main as mainmod


@pytest.fixture(autouse=True)
def _patch_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)
    monkeypatch.setattr(mainmod, "build_model", lambda config: TestModel(seed=0, call_tools=["read_document"]))


def _sse_event_types(resp: Any) -> list[str]:
    types: list[str] = []
    for line in resp.iter_lines():
        if line.startswith("event:"):
            types.append(line[len("event:"):].strip())
    return types


class _FakeUsage:
    input_tokens = 12
    output_tokens = 4
    total_tokens = 16


class _FakeRunResult:
    def __init__(self, output: str) -> None:
        self.output = output
        self.usage = _FakeUsage()


class _FakeUtilityAgent:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    async def run(self, prompt: str) -> _FakeRunResult:
        if "Titre :" in prompt:
            return _FakeRunResult('"Analyser les ventes Q2."')
        return _FakeRunResult("Décisions\n- Garder le plan Q2")


def test_agent_turn_sse_stream(tmp_path) -> None:
    payload = {
        "tenant_id": "t",
        "project_id": str(tmp_path),
        "project_path": str(tmp_path),
        "session_id": "s",
        "message": "lire",
        "history": [],
        "documents": [],
    }
    with TestClient(mainmod.app) as client:
        with client.stream(
            "POST",
            "/agent/turn",
            json=payload,
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        ) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            types = _sse_event_types(resp)

    assert "tool_call_start" in types
    assert "tool_call_result" in types
    assert types[-1] in {"done", "error"}


def test_util_title_and_summarize_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(utilitymod, "Agent", _FakeUtilityAgent)
    monkeypatch.setattr(utilitymod, "build_model", lambda _config: object())
    monkeypatch.setattr(utilitymod, "build_model_settings", lambda _config: {})

    headers = {"X-Internal-Secret": "desktop-dev-secret"}
    llm_config = {"provider": "mistral", "model": "mistral-small-latest"}
    with TestClient(mainmod.app) as client:
        title_resp = client.post(
            "/util/title",
            json={
                "first_user_message": "Analyse les ventes Q2",
                "first_assistant_reply": "Je vais comparer les chiffres.",
                "llm_provider_config": llm_config,
            },
            headers=headers,
        )
        summarize_resp = client.post(
            "/util/summarize",
            json={
                "messages": [
                    {"role": "user", "content": "Analyse les ventes Q2"},
                    {"role": "assistant", "content": "Le CA progresse."},
                ],
                "llm_provider_config": llm_config,
                "focus": "décisions",
            },
            headers=headers,
        )
        title_without_assistant_resp = client.post(
            "/util/title",
            json={
                "first_user_message": "Analyse les ventes Q2",
                "llm_provider_config": llm_config,
            },
            headers=headers,
        )

    assert title_resp.status_code == 200
    assert title_resp.json()["title"] == "Analyser les ventes Q2"
    assert title_without_assistant_resp.status_code == 200
    assert title_without_assistant_resp.json()["title"] == "Analyser les ventes Q2"
    assert summarize_resp.status_code == 200
    assert summarize_resp.json()["summary"]
    assert summarize_resp.json()["input_tokens"] == 12
    assert summarize_resp.json()["output_tokens"] == 4


def test_util_routes_require_internal_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(utilitymod, "Agent", _FakeUtilityAgent)
    monkeypatch.setattr(utilitymod, "build_model", lambda _config: object())
    monkeypatch.setattr(utilitymod, "build_model_settings", lambda _config: {})

    with TestClient(mainmod.app) as client:
        resp = client.post(
            "/util/title",
            json={
                "first_user_message": "Analyse les ventes Q2",
                "first_assistant_reply": "Je vais comparer les chiffres.",
                "llm_provider_config": {
                    "provider": "mistral",
                    "model": "mistral-small-latest",
                },
            },
        )

    assert resp.status_code == 401


def test_health_endpoint() -> None:
    with TestClient(mainmod.app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


def test_cors_preflight_options_passes_without_secret() -> None:
    """Le pré-vol CORS (OPTIONS) ne doit pas être bloqué par le secret interne :
    le navigateur n'envoie pas l'en-tête X-Internal-Secret sur un preflight."""
    with TestClient(mainmod.app) as client:
        resp = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5053",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "x-internal-secret",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") is not None


def test_to_sse_event_thinking_start() -> None:
    from app.main import to_sse_event
    from app.schemas import ThinkingStartEvent

    payload = to_sse_event(ThinkingStartEvent(thinking_id="think-0"))
    assert payload == {
        "event": "thinking_start",
        "data": '{"type":"thinking_start","thinking_id":"think-0"}',
    }


def test_agent_turn_construction_error_surfaces_as_sse_error(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Force une erreur de construction du modèle -> doit remonter en event SSE error,
    # pas en HTTP 500.
    def boom(_config: Any) -> Any:
        raise RuntimeError("bad llm config")

    monkeypatch.setattr(mainmod, "build_model", boom)

    payload = {
        "tenant_id": "t",
        "project_id": str(tmp_path),
        "project_path": str(tmp_path),
        "session_id": "s",
        "message": "lire",
        "history": [],
        "documents": [],
    }
    with TestClient(mainmod.app) as client:
        with client.stream(
            "POST",
            "/agent/turn",
            json=payload,
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        ) as resp:
            assert resp.status_code == 200
            assert _sse_event_types(resp)[-1] == "error"


async def _fake_personas_stream(**_kwargs: Any) -> Any:
    yield {"type": "done", "ok": True}


def test_personas_ask_closes_rag_store(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    close_calls: list[str] = []

    def fake_memory_store(
        _settings: Any,
        _ws_dir: Any,
        provider_set: Any = None,
        *,
        cloud_plugin_data_dir: Any = None,
    ) -> Any:
        from unittest.mock import MagicMock

        store = MagicMock(name="RagStore")
        store.close = MagicMock(side_effect=lambda: close_calls.append("close"))
        return store

    from app.plugins.workproba_personas import orchestrator as personas_orchestrator

    monkeypatch.setattr(mainmod, "_memory_store_for_workspace", fake_memory_store)
    monkeypatch.setattr(personas_orchestrator, "stream_ask", _fake_personas_stream)

    ws_dir = tmp_path / ".workproba"
    ws_dir.mkdir()
    plugin_dir = tmp_path / "plugins" / "workproba.personas"
    plugin_dir.mkdir(parents=True)

    payload = {
        "plugin_data_dir": str(plugin_dir),
        "persona_ids": ["01"],
        "question": "test?",
        "include_memory": True,
        "workspace_data_dir": str(ws_dir),
        "locale": "fr",
    }
    with TestClient(mainmod.app) as client:
        with client.stream(
            "POST",
            "/plugins/personas/ask",
            json=payload,
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        ) as resp:
            assert resp.status_code == 200
            for _ in resp.iter_lines():
                pass

    assert close_calls == ["close"]
