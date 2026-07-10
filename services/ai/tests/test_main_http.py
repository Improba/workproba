"""Test HTTP bout-en-bout de /agent/turn via TestClient + TestModel."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.models.test import TestModel

import app.auth as authmod
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


def test_health_endpoint() -> None:
    with TestClient(mainmod.app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


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
