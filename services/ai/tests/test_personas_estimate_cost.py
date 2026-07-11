"""Tests estimation coût personas (P1 V9)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.auth as authmod
import app.main as mainmod
from app.plugins.workproba_personas import estimate, manifest


@pytest.fixture(autouse=True)
def _patch_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)


@pytest.fixture
def plugin_dir(tmp_path: Path) -> Path:
    path = tmp_path / "plugins" / "workproba.personas"
    path.mkdir(parents=True)
    return path


def test_estimate_ask_mode() -> None:
    result = estimate.estimate_personas_cost(
        persona_ids=["01", "03"],
        mode="ask",
        locale="fr",
    )
    assert result["estimated_calls"] == 2
    assert result["estimated_tokens"] > 0
    assert result["warning"] is None


def test_estimate_meeting_mode_includes_synthesis() -> None:
    result = estimate.estimate_personas_cost(
        persona_ids=["01", "03", "04"],
        mode="meeting",
        rounds=3,
        locale="fr",
    )
    assert result["estimated_calls"] == 3 * 3 + 1
    assert result["rounds"] == 3


def test_estimate_meeting_caps_personas_and_rounds() -> None:
    result = estimate.estimate_personas_cost(
        persona_ids=["01", "02", "03", "04", "05", "06"],
        mode="meeting",
        rounds=10,
        locale="fr",
    )
    assert result["persona_count"] == manifest.MAX_PERSONAS
    assert result["rounds"] == manifest.MAX_ROUNDS
    assert result["warning"] is not None


def test_estimate_locked_mode_warning_at_cap() -> None:
    result = estimate.estimate_personas_cost(
        persona_ids=["01", "02", "03", "04", "05"],
        mode="meeting",
        rounds=5,
        settings_locked=True,
        locale="en",
    )
    assert result["warning"] is not None


def test_estimate_cost_endpoint(plugin_dir: Path) -> None:
    with TestClient(mainmod.app) as client:
        resp = client.post(
            "/plugins/personas/estimate-cost",
            json={
                "plugin_data_dir": str(plugin_dir),
                "persona_ids": ["01", "06"],
                "mode": "meeting",
                "rounds": 2,
            },
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["estimated_calls"] == 2 * 2 + 1
        assert body["estimated_tokens"] > 0


def test_estimate_cost_endpoint_requires_secret(plugin_dir: Path) -> None:
    with TestClient(mainmod.app) as client:
        resp = client.post(
            "/plugins/personas/estimate-cost",
            json={
                "plugin_data_dir": str(plugin_dir),
                "persona_ids": ["01"],
                "mode": "ask",
            },
        )
        assert resp.status_code == 401
