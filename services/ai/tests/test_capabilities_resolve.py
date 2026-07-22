"""Tests for pure capabilities entitlement resolver."""

from __future__ import annotations

from app.capabilities_resolve import (
    capability_ids_to_active_plugins,
    effective_managed_connector_ids,
    is_entitled,
    resolve_effective,
)
from app.plugins.registry import (
    PLUGIN_WORKPROBA_BROWSER,
    PLUGIN_WORKPROBA_CLOUD,
    PLUGIN_WORKPROBA_PERSONAS,
    PLUGIN_WORKPROBA_PROJET,
)

LOCAL_ENTITLED = frozenset(
    {
        "workproba_cloud",
        "projects",
        "regards",
        "web_navigation",
    }
)


def _ctx(
    *,
    machine_entitled_local_ids: frozenset[str] = LOCAL_ENTITLED,
    cloud_plugin_entitled: bool = True,
    cloud_allowlist: frozenset[str] = frozenset({"ihora", "echo"}),
    disabled_managed_connectors: frozenset[str] = frozenset(),
) -> dict[str, object]:
    return {
        "machine_entitled_local_ids": machine_entitled_local_ids,
        "cloud_plugin_entitled": cloud_plugin_entitled,
        "cloud_allowlist": cloud_allowlist,
        "disabled_managed_connectors": disabled_managed_connectors,
    }


def test_local_entitled_only_when_machine_entitled() -> None:
    ctx = _ctx(machine_entitled_local_ids=frozenset({"projects", "regards"}))

    assert is_entitled("projects", **ctx) is True
    assert is_entitled("regards", **ctx) is True
    assert is_entitled("web_navigation", **ctx) is False
    assert is_entitled("workproba_cloud", **ctx) is False


def test_managed_entitled_requires_cloud_plugin() -> None:
    ctx = _ctx(cloud_plugin_entitled=False)

    assert is_entitled("managed:ihora", **ctx) is False
    assert is_entitled("managed:echo", **ctx) is False


def test_managed_disabled_overrides_wanted() -> None:
    ctx = _ctx(disabled_managed_connectors=frozenset({"ihora"}))

    assert is_entitled("managed:ihora", **ctx) is False
    assert is_entitled("managed:echo", **ctx) is True


def test_managed_requires_allowlist() -> None:
    ctx = _ctx(cloud_allowlist=frozenset({"ihora"}))

    assert is_entitled("managed:ihora", **ctx) is True
    assert is_entitled("managed:echo", **ctx) is False


def test_resolve_effective_is_entitled_intersection_wanted() -> None:
    wanted = {
        "workproba_cloud": True,
        "projects": True,
        "regards": False,
        "web_navigation": True,
        "managed:ihora": True,
        "managed:echo": True,
        "managed:unknown": True,
    }
    ctx = _ctx(
        machine_entitled_local_ids=frozenset({"projects", "regards", "workproba_cloud"}),
        cloud_allowlist=frozenset({"ihora"}),
        disabled_managed_connectors=frozenset({"echo"}),
    )

    effective = resolve_effective(wanted, **ctx)

    assert effective == {"workproba_cloud", "projects", "managed:ihora"}
    assert wanted["managed:echo"] is True
    assert wanted["web_navigation"] is True


def test_parent_gate_cloud_off_blocks_managed_even_if_wanted() -> None:
    wanted = {
        "workproba_cloud": False,
        "managed:ihora": True,
        "regards": True,
    }
    ctx = _ctx(machine_entitled_local_ids=LOCAL_ENTITLED)

    effective = resolve_effective(wanted, **ctx)

    assert "managed:ihora" not in effective
    assert "regards" in effective
    assert "workproba_cloud" not in effective


def test_parent_gate_cloud_on_projects_off_managed_independent() -> None:
    wanted = {
        "workproba_cloud": True,
        "projects": False,
        "managed:ihora": True,
    }
    ctx = _ctx(machine_entitled_local_ids=LOCAL_ENTITLED)

    effective = resolve_effective(wanted, **ctx)

    assert "projects" not in effective
    assert "managed:ihora" in effective
    assert "workproba_cloud" in effective


def test_parent_gate_cloud_on_projects_on_ihora_off() -> None:
    from app.capabilities_resolve import (
        capability_ids_to_active_plugins,
        effective_managed_connector_ids,
    )

    wanted = {
        "workproba_cloud": True,
        "projects": True,
        "managed:ihora": False,
        "managed:echo": True,
    }
    ctx = _ctx(
        machine_entitled_local_ids=LOCAL_ENTITLED,
        cloud_allowlist=frozenset({"ihora", "echo"}),
    )

    effective = resolve_effective(wanted, **ctx)

    assert effective == {"workproba_cloud", "projects", "managed:echo"}
    plugins = capability_ids_to_active_plugins(effective)
    assert PLUGIN_WORKPROBA_PROJET in plugins
    assert PLUGIN_WORKPROBA_CLOUD in plugins
    assert effective_managed_connector_ids(effective) == frozenset({"echo"})
    assert "ihora" not in effective_managed_connector_ids(effective)


def test_apply_parent_gates_preserves_when_cloud_wanted() -> None:
    from app.capabilities_resolve import apply_parent_gates

    effective = {"workproba_cloud", "projects", "managed:ihora", "regards"}
    result = apply_parent_gates(effective, {"workproba_cloud": True})
    assert result == effective


def test_apply_parent_gates_strips_nested_when_cloud_unwanted() -> None:
    from app.capabilities_resolve import apply_parent_gates

    effective = {"projects", "managed:ihora", "regards", "web_navigation"}
    result = apply_parent_gates(effective, {"workproba_cloud": False})
    assert result == {"regards", "web_navigation"}


def test_cloud_off_no_managed_effective_even_if_wanted() -> None:
    wanted = {
        "workproba_cloud": True,
        "managed:ihora": True,
        "managed:echo": True,
    }
    ctx = _ctx(cloud_plugin_entitled=False)

    effective = resolve_effective(wanted, **ctx)

    assert effective == {"workproba_cloud"}
    assert "managed:ihora" not in effective
    assert "managed:echo" not in effective


def test_resolve_effective_does_not_mutate_wanted() -> None:
    wanted = {"projects": True, "managed:ihora": True}
    snapshot = dict(wanted)
    ctx = _ctx(cloud_plugin_entitled=False)

    resolve_effective(wanted, **ctx)

    assert wanted == snapshot


def test_capability_ids_to_active_plugins_maps_locals_and_cloud_for_managed() -> None:
    effective = {
        "projects",
        "regards",
        "managed:ihora",
    }

    plugins = capability_ids_to_active_plugins(effective)

    assert plugins == sorted(
        [
            PLUGIN_WORKPROBA_PROJET,
            PLUGIN_WORKPROBA_PERSONAS,
            PLUGIN_WORKPROBA_CLOUD,
        ]
    )


def test_capability_ids_to_active_plugins_locals_only() -> None:
    effective = {"web_navigation", "projects"}

    plugins = capability_ids_to_active_plugins(effective)

    assert plugins == sorted([PLUGIN_WORKPROBA_BROWSER, PLUGIN_WORKPROBA_PROJET])
    assert len(plugins) == 2


def test_effective_managed_connector_ids_strips_prefix() -> None:
    effective = {"projects", "managed:ihora", "managed:echo"}

    connectors = effective_managed_connector_ids(effective)

    assert connectors == frozenset({"ihora", "echo"})


def test_unknown_capability_id_is_never_entitled() -> None:
    ctx = _ctx()

    assert is_entitled("not_a_capability", **ctx) is False
    assert is_entitled("managed:", **ctx) is False
