"""Pure entitlement resolver for workspace capabilities."""

from __future__ import annotations

from collections.abc import Iterable

from app.capabilities_profile import (
    connector_id_from_managed_capability,
    is_managed_capability_id,
    is_valid_capability_id,
)
from app.plugins.registry import (
    PLUGIN_WORKPROBA_BROWSER,
    PLUGIN_WORKPROBA_CLOUD,
    PLUGIN_WORKPROBA_PERSONAS,
    PLUGIN_WORKPROBA_PROJET,
)

CAPABILITY_TO_PLUGIN_ID: dict[str, str] = {
    "workproba_cloud": PLUGIN_WORKPROBA_CLOUD,
    "projects": PLUGIN_WORKPROBA_PROJET,
    "regards": PLUGIN_WORKPROBA_PERSONAS,
    "web_navigation": PLUGIN_WORKPROBA_BROWSER,
}

# Nested under workproba_cloud in the space profile (independent toggles,
# but parent wanted must be True for them to become effective).
CLOUD_NESTED_LOCAL_IDS = frozenset({"projects"})


def _as_frozenset(values: frozenset[str] | Iterable[str]) -> frozenset[str]:
    if isinstance(values, frozenset):
        return values
    return frozenset(values)


def is_entitled(
    capability_id: str,
    *,
    machine_entitled_local_ids: frozenset[str] | Iterable[str],
    cloud_plugin_entitled: bool,
    cloud_allowlist: frozenset[str] | Iterable[str],
    disabled_managed_connectors: frozenset[str] | Iterable[str],
) -> bool:
    if not is_valid_capability_id(capability_id):
        return False

    if is_managed_capability_id(capability_id):
        connector_id = connector_id_from_managed_capability(capability_id)
        if not cloud_plugin_entitled:
            return False
        if connector_id in _as_frozenset(disabled_managed_connectors):
            return False
        return connector_id in _as_frozenset(cloud_allowlist)

    return capability_id in _as_frozenset(machine_entitled_local_ids)


def apply_parent_gates(effective: set[str], wanted: dict[str, bool]) -> set[str]:
    """Drop nested caps when parent workproba_cloud is not wanted in the space."""
    if wanted.get("workproba_cloud") is True:
        return set(effective)

    return {
        cap_id
        for cap_id in effective
        if cap_id not in CLOUD_NESTED_LOCAL_IDS and not is_managed_capability_id(cap_id)
    }


def resolve_effective(
    wanted: dict[str, bool],
    *,
    machine_entitled_local_ids: frozenset[str] | Iterable[str],
    cloud_plugin_entitled: bool,
    cloud_allowlist: frozenset[str] | Iterable[str],
    disabled_managed_connectors: frozenset[str] | Iterable[str],
) -> set[str]:
    ctx = {
        "machine_entitled_local_ids": _as_frozenset(machine_entitled_local_ids),
        "cloud_plugin_entitled": cloud_plugin_entitled,
        "cloud_allowlist": _as_frozenset(cloud_allowlist),
        "disabled_managed_connectors": _as_frozenset(disabled_managed_connectors),
    }
    entitled_wanted = {
        cap_id
        for cap_id, is_wanted in wanted.items()
        if is_wanted and is_entitled(cap_id, **ctx)
    }
    return apply_parent_gates(entitled_wanted, wanted)


def capability_ids_to_active_plugins(effective_ids: Iterable[str]) -> list[str]:
    plugins: set[str] = set()
    has_managed = False

    for cap_id in effective_ids:
        if is_managed_capability_id(cap_id):
            has_managed = True
            continue
        plugin_id = CAPABILITY_TO_PLUGIN_ID.get(cap_id)
        if plugin_id is not None:
            plugins.add(plugin_id)

    if has_managed:
        plugins.add(PLUGIN_WORKPROBA_CLOUD)

    return sorted(plugins)


def effective_managed_connector_ids(effective_ids: Iterable[str]) -> frozenset[str]:
    return frozenset(
        connector_id_from_managed_capability(cap_id)
        for cap_id in effective_ids
        if is_managed_capability_id(cap_id)
    )
