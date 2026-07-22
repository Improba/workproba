"""Tests for workspace capabilities profile store."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.capabilities_profile import (
    InvalidCapabilityIdError,
    capabilities_path,
    ensure_initialized,
    load,
    set_wanted,
)


def test_capabilities_path_is_workspace_root_file(tmp_path: Path) -> None:
    assert capabilities_path(tmp_path) == tmp_path / "capabilities.json"


def test_ensure_initialized_defaults_intersect_entitled(tmp_path: Path) -> None:
    entitled = {
        "workproba_cloud",
        "projects",
        "regards",
        "web_navigation",
        "managed:ihora",
        "managed:echo",
        "unknown_capability",
    }

    profile = ensure_initialized(tmp_path, entitled, initialized_from="defaults")

    assert profile.initialized_from == "defaults"
    assert profile.migrated_at is None
    assert profile.wanted == {
        "workproba_cloud": True,
        "projects": True,
        "regards": True,
        "managed:ihora": True,
    }

    on_disk = json.loads(capabilities_path(tmp_path).read_text(encoding="utf-8"))
    assert on_disk["version"] == 1
    assert on_disk["initializedFrom"] == "defaults"
    assert on_disk["migratedAt"] is None
    assert "updatedAt" in on_disk


def test_set_wanted_rejects_unknown_id(tmp_path: Path) -> None:
    ensure_initialized(tmp_path, {"regards"}, initialized_from="defaults")

    with pytest.raises(InvalidCapabilityIdError):
        set_wanted(tmp_path, {"not_a_capability": True})


def test_ensure_initialized_second_open_is_noop(tmp_path: Path) -> None:
    entitled = {"regards", "projects", "managed:ihora"}

    first = ensure_initialized(tmp_path, entitled, initialized_from="migration")
    path = capabilities_path(tmp_path)
    first_bytes = path.read_bytes()
    first_mtime = path.stat().st_mtime

    second = ensure_initialized(
        tmp_path,
        {"web_navigation", "managed:echo"},
        initialized_from="defaults",
    )

    assert second.wanted == first.wanted
    assert second.initialized_from == "migration"
    assert second.migrated_at == first.migrated_at
    assert path.read_bytes() == first_bytes
    assert path.stat().st_mtime == first_mtime


def test_set_wanted_preserves_other_entries(tmp_path: Path) -> None:
    ensure_initialized(
        tmp_path,
        {"regards", "projects", "managed:ihora"},
        initialized_from="defaults",
    )

    updated = set_wanted(tmp_path, {"regards": False, "web_navigation": True})

    assert updated.wanted["projects"] is True
    assert updated.wanted["managed:ihora"] is True
    assert updated.wanted["regards"] is False
    assert updated.wanted["web_navigation"] is True

    reloaded = load(tmp_path)
    assert reloaded is not None
    assert reloaded.wanted == updated.wanted
