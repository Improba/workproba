"""Tests preset enterprise (schéma + contexte AgentTurnRequest)."""

from __future__ import annotations

import json
from pathlib import Path

from app.schemas import AgentTurnRequest

NESTED_PRESET = {
    "preset_id": "improba-eti-rh-2026",
    "mode": "locked",
    "plugins": {
        "allowed": ["workproba.projet", "workproba.personas", "workproba.cloud"],
        "local_plugins": False,
    },
    "permissions": {
        "network": False,
        "code_execute": False,
        "project_sync": True,
        "network_improba_cloud": True,
    },
    "cloud": {
        "endpoint": "https://cloud.example.test",
        "org_id": "org-eti",
    },
    "ui": {
        "locale": "fr",
        "locale_locked": True,
    },
    "audit": {
        "enabled": True,
        "retention_days": 90,
    },
}


def _map_preset(raw: dict) -> dict:
    """Miroir simplifié du mapping Rust pour tests Python."""
    permissions = raw.get("permissions", {})
    cloud = raw.get("cloud", {})
    return {
        "settings_locked": raw.get("mode") == "locked",
        "locale_locked": bool(raw.get("ui", {}).get("locale_locked")),
        "locale": raw.get("ui", {}).get("locale"),
        "plugins_allowed": raw.get("plugins", {}).get("allowed"),
        "local_plugins_allowed": raw.get("plugins", {}).get("local_plugins"),
        "permissions_network": permissions.get("network"),
        "permissions_project_sync": permissions.get("project_sync"),
        "permissions_network_improba_cloud": permissions.get("network_improba_cloud"),
        "cloud_endpoint": cloud.get("endpoint"),
        "cloud_org_id": cloud.get("org_id"),
        "code_execute": permissions.get("code_execute"),
        "audit_retention_days": raw.get("audit", {}).get("retention_days"),
        "audit_enabled": raw.get("audit", {}).get("enabled"),
    }


def test_parse_nested_enterprise_preset_schema() -> None:
    mapped = _map_preset(NESTED_PRESET)
    assert mapped["settings_locked"] is True
    assert mapped["locale"] == "fr"
    assert mapped["permissions_network"] is False
    assert mapped["permissions_project_sync"] is True
    assert mapped["permissions_network_improba_cloud"] is True
    assert mapped["cloud_endpoint"] == "https://cloud.example.test"
    assert mapped["cloud_org_id"] == "org-eti"
    assert mapped["code_execute"] is False
    assert mapped["audit_retention_days"] == 90
    assert mapped["plugins_allowed"] == [
        "workproba.projet",
        "workproba.personas",
        "workproba.cloud",
    ]


def test_agent_turn_request_accepts_preset_context() -> None:
    payload = AgentTurnRequest(
        project_id="p",
        session_id="s",
        message="hello",
        settings_locked=True,
        permissions_network=False,
        code_execute=False,
        audit_retention_days=90,
        audit_enabled=True,
    )
    assert payload.settings_locked is True
    assert payload.permissions_network is False
    assert payload.code_execute is False
    assert payload.audit_retention_days == 90
    assert payload.audit_enabled is True


def test_enterprise_preset_file_roundtrip(tmp_path: Path) -> None:
    app_data = tmp_path / "app_data"
    presets = app_data / "presets"
    presets.mkdir(parents=True)
    preset_path = presets / "enterprise.json"
    preset_path.write_text(json.dumps(NESTED_PRESET), encoding="utf-8")
    loaded = json.loads(preset_path.read_text(encoding="utf-8"))
    mapped = _map_preset(loaded)
    assert mapped["settings_locked"] is True
    assert mapped["local_plugins_allowed"] is False


def test_permissions_network_blocks_browser_in_locked_mode() -> None:
    mapped = _map_preset(NESTED_PRESET)
    blocked = mapped["settings_locked"] and not mapped["permissions_network"]
    assert blocked is True


def test_code_execute_false_blocks_run_code_context() -> None:
    mapped = _map_preset(NESTED_PRESET)
    assert mapped["settings_locked"] and not mapped["code_execute"]
