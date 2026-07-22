"""Tests for turn-start capabilities snapshot (immutable mid-turn)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.capabilities_profile import ensure_initialized, set_wanted
from app.capabilities_turn import (
    machine_entitled_local_ids,
    resolve_turn_capabilities_snapshot,
)
from app.plugins.registry import (
    PLUGIN_WORKPROBA_BROWSER,
    PLUGIN_WORKPROBA_CLOUD,
    PLUGIN_WORKPROBA_PERSONAS,
    PLUGIN_WORKPROBA_PROJET,
)


@pytest.fixture
def plugins_root(tmp_path: Path) -> Path:
    root = tmp_path / "plugins"
    cloud = root / PLUGIN_WORKPROBA_CLOUD
    cloud.mkdir(parents=True)
    return root


async def _snapshot(
    workspace: Path,
    plugins_root: Path,
    *,
    payload_plugins: list[str] | None = None,
    allowlist: frozenset[str] | None = None,
) -> object:
    if allowlist is None:
        allowlist = frozenset({"ihora", "echo"})
    refresh = AsyncMock(return_value=allowlist)
    # Patch at the import site used inside resolve_turn_capabilities_snapshot.
    import app.plugins.workproba_cloud.plugin as cloud_plugin

    original = cloud_plugin.refresh_known_managed_connectors_cache
    cloud_plugin.refresh_known_managed_connectors_cache = refresh
    try:
        return await resolve_turn_capabilities_snapshot(
            workspace_data_dir=workspace,
            payload_active_plugins=payload_plugins
            or [
                PLUGIN_WORKPROBA_CLOUD,
                PLUGIN_WORKPROBA_PROJET,
                PLUGIN_WORKPROBA_PERSONAS,
            ],
            plugin_data_dir=plugins_root,
        )
    finally:
        cloud_plugin.refresh_known_managed_connectors_cache = original


@pytest.mark.asyncio
async def test_turn_snapshot_uses_space_profile_not_payload(
    tmp_path: Path, plugins_root: Path
) -> None:
    workspace = tmp_path / "space"
    workspace.mkdir()
    ensure_initialized(
        workspace,
        {
            "workproba_cloud",
            "projects",
            "regards",
            "managed:ihora",
        },
        initialized_from="migration",
    )
    set_wanted(
        workspace,
        {
            "workproba_cloud": True,
            "projects": True,
            "regards": False,
            "managed:ihora": True,
        },
    )

    # Payload still sends machine-global plugins including regards.
    snap = await _snapshot(
        workspace,
        plugins_root,
        payload_plugins=[
            PLUGIN_WORKPROBA_CLOUD,
            PLUGIN_WORKPROBA_PROJET,
            PLUGIN_WORKPROBA_PERSONAS,
        ],
    )

    assert PLUGIN_WORKPROBA_PROJET in snap.active_plugins
    assert PLUGIN_WORKPROBA_CLOUD in snap.active_plugins
    assert PLUGIN_WORKPROBA_PERSONAS not in snap.active_plugins
    assert snap.managed_allowed_connector_ids == frozenset({"ihora"})
    assert "managed:ihora" in snap.effective_ids
    assert "regards" not in snap.effective_ids


@pytest.mark.asyncio
async def test_turn_snapshot_frozen_until_next_turn(
    tmp_path: Path, plugins_root: Path
) -> None:
    workspace = tmp_path / "space"
    workspace.mkdir()
    ensure_initialized(
        workspace,
        {"workproba_cloud", "projects", "managed:ihora", "regards"},
        initialized_from="migration",
    )
    set_wanted(
        workspace,
        {
            "workproba_cloud": True,
            "projects": True,
            "managed:ihora": True,
            "regards": True,
        },
    )

    turn_a = await _snapshot(workspace, plugins_root)
    assert PLUGIN_WORKPROBA_PERSONAS in turn_a.active_plugins
    assert "ihora" in turn_a.managed_allowed_connector_ids

    # Mid-turn (or between) profile mutation must not alter turn A snapshot object.
    set_wanted(
        workspace,
        {
            "regards": False,
            "managed:ihora": False,
            "projects": False,
        },
    )

    assert PLUGIN_WORKPROBA_PERSONAS in turn_a.active_plugins
    assert "ihora" in turn_a.managed_allowed_connector_ids
    assert "projects" in turn_a.effective_ids

    turn_b = await _snapshot(workspace, plugins_root)
    assert PLUGIN_WORKPROBA_PERSONAS not in turn_b.active_plugins
    assert "ihora" not in turn_b.managed_allowed_connector_ids
    assert "projects" not in turn_b.effective_ids
    assert PLUGIN_WORKPROBA_CLOUD in turn_b.active_plugins


@pytest.mark.asyncio
async def test_turn_nested_independent_under_cloud_parent(
    tmp_path: Path, plugins_root: Path
) -> None:
    workspace = tmp_path / "space"
    workspace.mkdir()
    ensure_initialized(
        workspace,
        {"workproba_cloud", "projects", "managed:ihora", "managed:echo"},
        initialized_from="migration",
    )
    set_wanted(
        workspace,
        {
            "workproba_cloud": True,
            "projects": False,
            "managed:ihora": True,
            "managed:echo": False,
        },
    )

    snap = await _snapshot(workspace, plugins_root)
    assert PLUGIN_WORKPROBA_PROJET not in snap.active_plugins
    assert PLUGIN_WORKPROBA_CLOUD in snap.active_plugins
    assert snap.managed_allowed_connector_ids == frozenset({"ihora"})


@pytest.mark.asyncio
async def test_turn_cloud_wanted_false_blocks_nested(
    tmp_path: Path, plugins_root: Path
) -> None:
    workspace = tmp_path / "space"
    workspace.mkdir()
    ensure_initialized(
        workspace,
        {"workproba_cloud", "projects", "managed:ihora", "regards"},
        initialized_from="migration",
    )
    set_wanted(
        workspace,
        {
            "workproba_cloud": False,
            "projects": True,
            "managed:ihora": True,
            "regards": True,
        },
    )

    snap = await _snapshot(workspace, plugins_root)
    assert "managed:ihora" not in snap.effective_ids
    assert "projects" not in snap.effective_ids
    assert PLUGIN_WORKPROBA_PROJET not in snap.active_plugins
    assert snap.managed_allowed_connector_ids == frozenset()
    assert PLUGIN_WORKPROBA_PERSONAS in snap.active_plugins


@pytest.mark.asyncio
async def test_turn_snapshot_frozen_across_provider_attempts(
    tmp_path: Path, plugins_root: Path
) -> None:
    """Single resolve before attempts: mid-turn wanted PUT must not change attempt 2."""
    workspace = tmp_path / "space"
    workspace.mkdir()
    machine_plugins = [
        PLUGIN_WORKPROBA_CLOUD,
        PLUGIN_WORKPROBA_PROJET,
        PLUGIN_WORKPROBA_PERSONAS,
    ]
    ensure_initialized(
        workspace,
        {"workproba_cloud", "projects", "regards", "managed:ihora"},
        initialized_from="migration",
    )
    set_wanted(
        workspace,
        {
            "workproba_cloud": True,
            "projects": True,
            "regards": False,
            "managed:ihora": True,
        },
    )

    turn_snapshot = await _snapshot(
        workspace,
        plugins_root,
        payload_plugins=machine_plugins,
    )
    assert PLUGIN_WORKPROBA_PERSONAS not in turn_snapshot.active_plugins
    assert "regards" not in turn_snapshot.effective_ids

    # Simulate attempt 1 overwriting payload.active_plugins for the turn.
    attempt_payload_plugins = list(turn_snapshot.active_plugins)

    # Mid-turn wanted PUT (would affect a second resolve).
    set_wanted(
        workspace,
        {
            "regards": True,
            "managed:ihora": False,
        },
    )

    reresolved = await _snapshot(
        workspace,
        plugins_root,
        payload_plugins=attempt_payload_plugins,
    )
    assert reresolved.effective_ids != turn_snapshot.effective_ids

    # Correct pattern: reuse the first snapshot, do not re-resolve.
    assert PLUGIN_WORKPROBA_PERSONAS not in turn_snapshot.active_plugins
    assert "regards" not in turn_snapshot.effective_ids
    assert "ihora" in turn_snapshot.managed_allowed_connector_ids


@pytest.mark.asyncio
async def test_machine_off_hub_plugin_excluded_despite_wanted(
    tmp_path: Path, plugins_root: Path
) -> None:
    workspace = tmp_path / "space"
    workspace.mkdir()
    ensure_initialized(
        workspace,
        {
            "workproba_cloud",
            "projects",
            "regards",
            "web_navigation",
            "managed:ihora",
        },
        initialized_from="migration",
    )
    set_wanted(
        workspace,
        {
            "workproba_cloud": True,
            "projects": True,
            "regards": True,
            "web_navigation": True,
            "managed:ihora": True,
        },
    )

    # Hub machine-off: cloud and browser absent from machine active_plugins.
    snap = await _snapshot(
        workspace,
        plugins_root,
        payload_plugins=[PLUGIN_WORKPROBA_PROJET, PLUGIN_WORKPROBA_PERSONAS],
        allowlist=frozenset({"ihora"}),
    )

    assert PLUGIN_WORKPROBA_CLOUD not in snap.active_plugins
    assert PLUGIN_WORKPROBA_BROWSER not in snap.active_plugins
    assert "workproba_cloud" not in snap.effective_ids
    assert "web_navigation" not in snap.effective_ids
    assert "managed:ihora" not in snap.effective_ids
    assert snap.managed_allowed_connector_ids == frozenset()
    assert "projects" in snap.effective_ids
    assert "regards" in snap.effective_ids


def test_machine_entitled_local_ids_requires_machine_active_plugin() -> None:
    entitled = machine_entitled_local_ids(
        [PLUGIN_WORKPROBA_PROJET, PLUGIN_WORKPROBA_PERSONAS]
    )
    assert entitled == frozenset({"projects", "regards"})
    assert "workproba_cloud" not in entitled
    assert "web_navigation" not in entitled
