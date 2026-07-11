"""Tests API core plugins et dispatch hooks."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.i18n import t
from app.plugins.core import CoreAPI, clear_cross_audit_log, cross_audit_log
from app.plugins.hooks import HookRegistry, PluginContext
from app.plugins.registry import (
    PLUGIN_WORKPROBA_PROJET,
    build_plugin_contexts,
    get_builtin_plugins,
    is_plugin_active,
    register_plugin_hooks,
)


def test_builtin_plugins_manifest() -> None:
    plugins = get_builtin_plugins()
    assert PLUGIN_WORKPROBA_PROJET in plugins
    manifest = plugins[PLUGIN_WORKPROBA_PROJET]
    assert "storage:namespace" in manifest.permissions
    assert "publish_artifact" in manifest.tools


def test_is_plugin_active_retrocompat() -> None:
    assert is_plugin_active(PLUGIN_WORKPROBA_PROJET, None) is False
    assert is_plugin_active(PLUGIN_WORKPROBA_PROJET, []) is False
    assert is_plugin_active(PLUGIN_WORKPROBA_PROJET, ["workproba.projet"]) is True


def test_core_storage_get_set(tmp_path: Path) -> None:
    ctx = PluginContext(
        plugin_id=PLUGIN_WORKPROBA_PROJET,
        plugin_data_dir=tmp_path,
        locale="fr",
        provider_set=None,
        permissions=frozenset({"storage:namespace"}),
    )
    core = CoreAPI.for_plugin(ctx)
    assert core.storage.path() == tmp_path
    core.storage.set("hello", {"n": 1})
    assert core.storage.get("hello") == {"n": 1}


def test_core_i18n_uses_merged_messages() -> None:
    ctx = PluginContext(
        plugin_id=PLUGIN_WORKPROBA_PROJET,
        plugin_data_dir=Path("/tmp"),
        locale="fr",
        provider_set=None,
    )
    core = CoreAPI.for_plugin(ctx)
    text = core.i18n.t("human.publish_artifact.done", name="doc.pdf", project="Alpha")
    assert "doc.pdf" in text
    assert "Alpha" in text
    assert text == t("fr", "human.publish_artifact.done", name="doc.pdf", project="Alpha")


def test_core_storage_cross_requires_permission(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir()
    target_dir.mkdir()

    ctx = PluginContext(
        plugin_id="workproba.cloud",
        plugin_data_dir=source_dir,
        locale="fr",
        provider_set=None,
        permissions=frozenset(),
    )
    core = CoreAPI.for_plugin(ctx)
    with pytest.raises(PermissionError):
        core.storage.cross("target", "get", "k")


def test_core_storage_cross_audited(tmp_path: Path) -> None:
    clear_cross_audit_log()
    source_dir = tmp_path / "workproba.cloud"
    target_dir = tmp_path / "workproba.projet"
    source_dir.mkdir()
    target_dir.mkdir()

    ctx = PluginContext(
        plugin_id="workproba.cloud",
        plugin_data_dir=source_dir,
        locale="fr",
        provider_set=None,
        permissions=frozenset({"storage:cross:workproba.projet"}),
    )
    core = CoreAPI.for_plugin(ctx)
    core.storage.cross("workproba.projet", "set", "sync", {"ok": True})
    value = core.storage.cross("workproba.projet", "get", "sync")
    assert value == {"ok": True}
    audit = cross_audit_log()
    assert len(audit) == 2
    assert audit[0]["target"] == "workproba.projet"


def test_hook_registry_dispatch_sync() -> None:
    registry = HookRegistry()
    calls: list[str] = []

    def handler(ctx: PluginContext, payload: dict) -> None:
        calls.append(f"{ctx.plugin_id}:{payload.get('tool')}")

    registry.subscribe(PLUGIN_WORKPROBA_PROJET, "tool.call_completed", handler)
    ctx = PluginContext(
        plugin_id=PLUGIN_WORKPROBA_PROJET,
        plugin_data_dir=Path("/tmp"),
        locale="fr",
        provider_set=None,
    )
    registry.dispatch(
        "tool.call_completed",
        {
            "tool": "publish_artifact",
            "_plugin_contexts": {PLUGIN_WORKPROBA_PROJET: ctx},
        },
    )
    assert calls == ["workproba.projet:publish_artifact"]


def test_build_plugin_contexts_requires_data_dir(tmp_path: Path) -> None:
    contexts = build_plugin_contexts(
        active_plugins=["workproba.projet"],
        plugin_data_dir=None,
        locale="fr",
        provider_set=None,
    )
    assert contexts == {}

    plugin_dir = tmp_path / "plugins" / "workproba.projet"
    plugin_dir.mkdir(parents=True)
    contexts = build_plugin_contexts(
        active_plugins=["workproba.projet"],
        plugin_data_dir=plugin_dir,
        locale="en",
        provider_set=None,
    )
    assert PLUGIN_WORKPROBA_PROJET in contexts
    assert contexts[PLUGIN_WORKPROBA_PROJET].locale == "en"


def test_build_plugin_contexts_from_browser_data_dir(tmp_path: Path) -> None:
    browser_dir = tmp_path / "plugins" / "workproba.browser"
    browser_dir.mkdir(parents=True)
    contexts = build_plugin_contexts(
        active_plugins=["workproba.browser", "workproba.personas"],
        plugin_data_dir=browser_dir,
        locale="fr",
        provider_set=None,
    )
    assert contexts["workproba.browser"].plugin_data_dir == browser_dir
    assert contexts["workproba.personas"].plugin_data_dir == (
        tmp_path / "plugins" / "workproba.personas"
    )


def test_register_plugin_hooks_idempotent() -> None:
    register_plugin_hooks(["workproba.projet"])
    register_plugin_hooks(None)
