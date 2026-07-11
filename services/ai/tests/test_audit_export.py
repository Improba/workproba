"""Tests export CSV du journal d'audit."""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.auth as authmod
import app.main as mainmod
from app.audit import audit_file_path, export_audit_csv, log_event

INTERNAL_HEADERS = {"X-Internal-Secret": "desktop-dev-secret"}


@pytest.fixture(autouse=True)
def _patch_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)


def _app_data(tmp_path: Path) -> Path:
    app_data = tmp_path / "app_data"
    app_data.mkdir()
    (app_data / "spaces" / "space-1").mkdir(parents=True)
    return app_data


def _parse_csv(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))


def test_export_audit_csv_format_and_columns(tmp_path: Path) -> None:
    app_data = _app_data(tmp_path)
    log_event(
        app_data,
        "browser.navigate",
        "agent",
        {"url": "https://example.com", "note": 'quote "test"'},
    )
    csv_text = export_audit_csv(app_data)
    rows = _parse_csv(csv_text)
    assert rows[0] == ["timestamp", "event", "actor", "details"]
    assert len(rows) == 2
    assert rows[1][1] == "browser.navigate"
    assert rows[1][2] == "agent"
    details = json.loads(rows[1][3])
    assert details["url"] == "https://example.com"
    assert details["note"] == 'quote "test"'


def test_export_audit_csv_filters(tmp_path: Path) -> None:
    app_data = _app_data(tmp_path)
    old_ts = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    recent_ts = datetime.now(UTC).isoformat()
    audit_path = audit_file_path(app_data)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({"timestamp": old_ts, "event": "old", "actor": "user", "details": {}}),
        json.dumps(
            {
                "timestamp": recent_ts,
                "event": "publish_artifact",
                "actor": "user",
                "details": {"name": "doc.pdf"},
            }
        ),
    ]
    audit_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    cutoff = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    filtered = export_audit_csv(
        app_data,
        from_ts=cutoff,
        event="publish_artifact",
    )
    rows = _parse_csv(filtered)
    assert len(rows) == 2
    assert rows[1][1] == "publish_artifact"
    assert json.loads(rows[1][3])["name"] == "doc.pdf"


def test_audit_export_http_endpoint(tmp_path: Path) -> None:
    app_data = _app_data(tmp_path)
    workspace = app_data / "spaces" / "space-1"
    log_event(app_data, "plugin.activated", "user", {"plugin_id": "workproba.browser"})
    with TestClient(mainmod.app) as client:
        response = client.get(
            "/audit/export",
            params={"workspace_data_dir": str(workspace), "format": "csv"},
            headers=INTERNAL_HEADERS,
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert 'filename="workproba-audit.csv"' in response.headers.get(
            "content-disposition", ""
        )
        rows = _parse_csv(response.text)
        assert rows[0] == ["timestamp", "event", "actor", "details"]
        assert rows[1][1] == "plugin.activated"


def test_audit_export_escapes_commas_and_quotes(tmp_path: Path) -> None:
    app_data = _app_data(tmp_path)
    log_event(
        app_data,
        "publish_artifact",
        "user",
        {"name": 'rapport, "final".pdf', "project_id": "p1"},
    )
    csv_text = export_audit_csv(app_data)
    rows = _parse_csv(csv_text)
    details = json.loads(rows[1][3])
    assert details["name"] == 'rapport, "final".pdf'
