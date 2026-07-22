"""Turn-start capabilities snapshot (immutable for the duration of the turn)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.capabilities_profile import (
    LOCAL_CAPABILITY_IDS,
    ensure_initialized,
)
from app.capabilities_resolve import (
    CAPABILITY_TO_PLUGIN_ID,
    capability_ids_to_active_plugins,
    effective_managed_connector_ids,
    resolve_effective,
)
from app.plugins.registry import (
    PLUGIN_WORKPROBA_CLOUD,
    get_builtin_plugins,
    is_plugin_active,
    resolve_plugin_data_dir,
)


@dataclass(frozen=True)
class TurnCapabilitiesSnapshot:
    """Frozen for one agent turn; mid-turn profile mutations do not apply."""

    active_plugins: list[str]
    managed_allowed_connector_ids: frozenset[str]
    effective_ids: frozenset[str]


def machine_entitled_local_ids(
    payload_active_plugins: list[str] | None,
) -> frozenset[str]:
    """V1: locals are entitled only when their plugin is machine-active."""
    payload = set(payload_active_plugins or [])
    entitled: set[str] = set()
    for cap_id, plugin_id in CAPABILITY_TO_PLUGIN_ID.items():
        if plugin_id in payload:
            entitled.add(cap_id)
    return frozenset(cap_id for cap_id in entitled if cap_id in LOCAL_CAPABILITY_IDS)


def cloud_plugin_entitled(
    payload_active_plugins: list[str] | None,
    cloud_dir: Path | None,
) -> bool:
    _ = cloud_dir
    return is_plugin_active(PLUGIN_WORKPROBA_CLOUD, payload_active_plugins)


def build_entitled_ids_for_migration(
    *,
    local_ids: frozenset[str],
    cloud_allowlist: frozenset[str],
    disabled_managed_connectors: frozenset[str],
    cloud_entitled: bool,
) -> list[str]:
    ids: list[str] = sorted(local_ids)
    if cloud_entitled:
        for connector_id in sorted(cloud_allowlist):
            if connector_id not in disabled_managed_connectors:
                ids.append(f"managed:{connector_id}")
    return ids


async def resolve_turn_capabilities_snapshot(
    *,
    workspace_data_dir: Path,
    payload_active_plugins: list[str] | None,
    plugin_data_dir: Path | None,
) -> TurnCapabilitiesSnapshot:
    """Load/migrate space profile, resolve effective, freeze turn plugins/connectors.

    Does not write ``wanted`` from the agent. Source of truth is capabilities.json
    under ``workspace_data_dir`` (never UI focus).
    """
    cloud_dir = resolve_plugin_data_dir(PLUGIN_WORKPROBA_CLOUD, plugin_data_dir)

    cloud_allowlist: frozenset[str] = frozenset()
    disabled: frozenset[str] = frozenset()
    if cloud_dir is not None:
        from app.plugins.workproba_cloud import storage as cloud_storage
        from app.plugins.workproba_cloud.plugin import (
            refresh_known_managed_connectors_cache,
        )

        cloud_allowlist = await refresh_known_managed_connectors_cache(cloud_dir)
        disabled = frozenset(cloud_storage.get_disabled_managed_connectors(cloud_dir))

    local_ids = machine_entitled_local_ids(payload_active_plugins)
    cloud_entitled = cloud_plugin_entitled(payload_active_plugins, cloud_dir)
    entitled_ids = build_entitled_ids_for_migration(
        local_ids=local_ids,
        cloud_allowlist=cloud_allowlist,
        disabled_managed_connectors=disabled,
        cloud_entitled=cloud_entitled,
    )

    profile = ensure_initialized(
        workspace_data_dir,
        entitled_ids,
        initialized_from="migration",
    )
    effective = resolve_effective(
        profile.wanted,
        machine_entitled_local_ids=local_ids,
        cloud_plugin_entitled=cloud_entitled,
        cloud_allowlist=cloud_allowlist,
        disabled_managed_connectors=disabled,
    )
    active_plugins = capability_ids_to_active_plugins(effective)
    # Technically loadable: intersection with builtin registry.
    builtins = set(get_builtin_plugins())
    active_plugins = [plugin_id for plugin_id in active_plugins if plugin_id in builtins]

    managed_allowed = effective_managed_connector_ids(effective)
    # Already gated by allowlist in resolve_effective; keep intersection explicit.
    managed_allowed = frozenset(managed_allowed & cloud_allowlist)

    return TurnCapabilitiesSnapshot(
        active_plugins=active_plugins,
        managed_allowed_connector_ids=managed_allowed,
        effective_ids=frozenset(effective),
    )
