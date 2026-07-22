"""API helpers for space capabilities profile (wanted UI read/write)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from app.capabilities_profile import (
    LOCAL_CAPABILITY_IDS,
    CapabilitiesProfile,
    ensure_initialized,
    is_managed_capability_id,
    set_wanted,
)
from app.capabilities_resolve import (
    CLOUD_NESTED_LOCAL_IDS,
    is_entitled,
    resolve_effective,
)
from app.capabilities_turn import (
    build_entitled_ids_for_migration,
    cloud_plugin_entitled,
    machine_entitled_local_ids,
)
from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD, resolve_plugin_data_dir

SpaceCapabilityStatus = Literal["active", "available", "unavailable"]

UnavailableReason = Literal[
    "not_entitled",
    "parent_cloud_off",
    "cloud_not_ready",
    "machine_disabled",
]


@dataclass(frozen=True)
class SpaceCapabilityItem:
    id: str
    status: SpaceCapabilityStatus
    wanted: bool
    entitled: bool
    unavailable_reason: UnavailableReason | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "wanted": self.wanted,
            "entitled": self.entitled,
            "unavailableReason": self.unavailable_reason,
        }


@dataclass(frozen=True)
class SpaceCapabilitiesView:
    wanted: dict[str, bool]
    items: list[SpaceCapabilityItem]
    effective_ids: frozenset[str]
    cloud_wanted: bool
    cloud_entitled: bool

    def to_json(self) -> dict[str, Any]:
        return {
            "wanted": dict(self.wanted),
            "items": [item.to_json() for item in self.items],
            "effectiveIds": sorted(self.effective_ids),
            "cloudWanted": self.cloud_wanted,
            "cloudEntitled": self.cloud_entitled,
        }


def _is_cloud_nested(capability_id: str) -> bool:
    return capability_id in CLOUD_NESTED_LOCAL_IDS or is_managed_capability_id(
        capability_id
    )


async def _load_cloud_context(
    plugin_data_dir: Path | None,
) -> tuple[frozenset[str], frozenset[str], Path | None]:
    cloud_dir = resolve_plugin_data_dir(PLUGIN_WORKPROBA_CLOUD, plugin_data_dir)
    cloud_allowlist: frozenset[str] = frozenset()
    disabled: frozenset[str] = frozenset()
    if cloud_dir is None:
        return cloud_allowlist, disabled, None

    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.plugins.workproba_cloud.plugin import refresh_known_managed_connectors_cache

    cloud_allowlist = await refresh_known_managed_connectors_cache(cloud_dir)
    disabled = frozenset(cloud_storage.get_disabled_managed_connectors(cloud_dir))
    return cloud_allowlist, disabled, cloud_dir


def _classify_item(
    capability_id: str,
    *,
    wanted: dict[str, bool],
    effective: set[str],
    entitled: bool,
    cloud_wanted: bool,
    cloud_entitled: bool,
) -> SpaceCapabilityItem:
    is_wanted = wanted.get(capability_id) is True
    if capability_id in effective:
        return SpaceCapabilityItem(
            id=capability_id,
            status="active",
            wanted=is_wanted,
            entitled=True,
        )

    if not entitled:
        reason: UnavailableReason = "not_entitled"
        if _is_cloud_nested(capability_id) and not cloud_entitled:
            reason = "cloud_not_ready"
        return SpaceCapabilityItem(
            id=capability_id,
            status="unavailable",
            wanted=is_wanted,
            entitled=False,
            unavailable_reason=reason,
        )

    # Entitled but not effective: parent gate or simply not wanted.
    if _is_cloud_nested(capability_id) and not cloud_wanted:
        return SpaceCapabilityItem(
            id=capability_id,
            status="unavailable",
            wanted=is_wanted,
            entitled=True,
            unavailable_reason="parent_cloud_off",
        )

    if is_wanted:
        # Wanted + entitled but still not effective: treat as unavailable machine gate.
        return SpaceCapabilityItem(
            id=capability_id,
            status="unavailable",
            wanted=True,
            entitled=True,
            unavailable_reason="machine_disabled",
        )

    return SpaceCapabilityItem(
        id=capability_id,
        status="available",
        wanted=False,
        entitled=True,
    )


def _ordered_capability_ids(
    *,
    local_ids: frozenset[str],
    cloud_allowlist: frozenset[str],
    disabled: frozenset[str],
    wanted: dict[str, bool],
) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()

    def add(cap_id: str) -> None:
        if cap_id in seen:
            return
        seen.add(cap_id)
        ids.append(cap_id)

    for cap_id in (
        "workproba_cloud",
        "projects",
        "regards",
        "web_navigation",
    ):
        if cap_id in local_ids or cap_id in LOCAL_CAPABILITY_IDS:
            add(cap_id)

    for connector_id in sorted(cloud_allowlist):
        if connector_id in disabled:
            continue
        add(f"managed:{connector_id}")

    # Keep wanted managed ids visible even if temporarily not in allowlist.
    for cap_id in sorted(wanted):
        if is_managed_capability_id(cap_id):
            add(cap_id)

    return ids


async def load_space_capabilities_view(
    *,
    workspace_data_dir: Path,
    payload_active_plugins: list[str] | None,
    plugin_data_dir: Path | None,
) -> SpaceCapabilitiesView:
    cloud_allowlist, disabled, cloud_dir = await _load_cloud_context(plugin_data_dir)
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
    return build_space_capabilities_view(
        profile,
        machine_entitled_local_ids=local_ids,
        cloud_plugin_entitled=cloud_entitled,
        cloud_allowlist=cloud_allowlist,
        disabled_managed_connectors=disabled,
    )


def build_space_capabilities_view(
    profile: CapabilitiesProfile,
    *,
    machine_entitled_local_ids: frozenset[str],
    cloud_plugin_entitled: bool,
    cloud_allowlist: frozenset[str],
    disabled_managed_connectors: frozenset[str],
) -> SpaceCapabilitiesView:
    ctx = {
        "machine_entitled_local_ids": machine_entitled_local_ids,
        "cloud_plugin_entitled": cloud_plugin_entitled,
        "cloud_allowlist": cloud_allowlist,
        "disabled_managed_connectors": disabled_managed_connectors,
    }
    effective = resolve_effective(profile.wanted, **ctx)
    cloud_wanted = profile.wanted.get("workproba_cloud") is True
    ordered = _ordered_capability_ids(
        local_ids=machine_entitled_local_ids,
        cloud_allowlist=cloud_allowlist,
        disabled=disabled_managed_connectors,
        wanted=profile.wanted,
    )
    items = [
        _classify_item(
            cap_id,
            wanted=profile.wanted,
            effective=effective,
            entitled=is_entitled(cap_id, **ctx),
            cloud_wanted=cloud_wanted,
            cloud_entitled=cloud_plugin_entitled,
        )
        for cap_id in ordered
    ]
    return SpaceCapabilitiesView(
        wanted=dict(profile.wanted),
        items=items,
        effective_ids=frozenset(effective),
        cloud_wanted=cloud_wanted,
        cloud_entitled=cloud_plugin_entitled,
    )


def apply_wanted_updates(
    workspace_data_dir: Path,
    updates: dict[str, bool],
    *,
    auto_want_cloud_parent: bool = True,
) -> CapabilitiesProfile:
    """Write wanted updates; optionally auto-enable workproba_cloud for nested ons."""
    normalized = dict(updates)
    if auto_want_cloud_parent:
        for cap_id, value in updates.items():
            if value and _is_cloud_nested(cap_id):
                normalized["workproba_cloud"] = True
                break
    return set_wanted(workspace_data_dir, normalized)
