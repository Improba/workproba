"""Tests ProjectSyncPort (PR 4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD, PLUGIN_WORKPROBA_PROJET
from app.plugins.workproba_projet import storage as projet_storage
from app.plugins.workproba_projet.sync_port import (
    PROJECT_SYNC_PERMISSION,
    clear_sync_audit_log,
    open_project_sync_port,
    sync_audit_log,
)


def _layout(tmp_path: Path) -> tuple[Path, Path, str]:
    plugins_root = tmp_path / "app_data" / "plugins"
    projet_dir = plugins_root / PLUGIN_WORKPROBA_PROJET
    projet_dir.mkdir(parents=True)
    project = projet_storage.create_project(projet_dir, "Alpha")
    project_id = str(project["id"])
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = workspace / "doc.txt"
    source.write_text("hello", encoding="utf-8")
    projet_storage.publish_artifact(
        plugin_data_dir=projet_dir,
        workspace_root=workspace,
        source_path="doc.txt",
        project_id=project_id,
        name="doc.txt",
    )
    return plugins_root, projet_dir, project_id


def test_open_project_sync_port_requires_permission(tmp_path: Path) -> None:
    plugins_root, _, _ = _layout(tmp_path)
    with pytest.raises(PermissionError, match=PROJECT_SYNC_PERMISSION):
        open_project_sync_port(
            caller_plugin_id=PLUGIN_WORKPROBA_CLOUD,
            caller_permissions=frozenset({"storage:namespace"}),
            plugins_root=plugins_root,
        )


def test_project_sync_port_lists_and_reads_artefacts(tmp_path: Path) -> None:
    clear_sync_audit_log()
    plugins_root, _, project_id = _layout(tmp_path)
    port = open_project_sync_port(
        caller_plugin_id=PLUGIN_WORKPROBA_CLOUD,
        caller_permissions=frozenset({PROJECT_SYNC_PERMISSION}),
        plugins_root=plugins_root,
    )

    projects = port.list_projects()
    assert any(p.get("id") == project_id for p in projects)

    artefacts = port.list_artefacts(project_id)
    assert len(artefacts) == 1
    assert artefacts[0]["name"] == "doc.txt"

    content = port.read_blob(f"{project_id}/doc.txt")
    assert content == b"hello"
    assert port.read_artefact(project_id, "doc.txt") == b"hello"

    changes = port.list_changes()
    assert len(changes["changes"]) == 1
    assert changes["changes"][0]["blob_id"] == f"{project_id}/doc.txt"

    audit = sync_audit_log()
    ops = {entry["op"] for entry in audit}
    assert "list_projects" in ops
    assert "list_artefacts" in ops
    assert "read_blob" in ops
    assert "list_changes" in ops
    assert all(entry["caller"] == PLUGIN_WORKPROBA_CLOUD for entry in audit)


def test_read_blob_rejects_invalid_blob_id(tmp_path: Path) -> None:
    plugins_root, _, _ = _layout(tmp_path)
    port = open_project_sync_port(
        caller_plugin_id=PLUGIN_WORKPROBA_CLOUD,
        caller_permissions=frozenset({PROJECT_SYNC_PERMISSION}),
        plugins_root=plugins_root,
    )
    with pytest.raises(ValueError, match="invalid_blob_id"):
        port.read_blob("missing-slash")


def test_apply_remote_change_not_available_in_v2(tmp_path: Path) -> None:
    plugins_root, _, _ = _layout(tmp_path)
    port = open_project_sync_port(
        caller_plugin_id=PLUGIN_WORKPROBA_CLOUD,
        caller_permissions=frozenset({PROJECT_SYNC_PERMISSION}),
        plugins_root=plugins_root,
    )
    with pytest.raises(NotImplementedError):
        port.apply_remote_change({"project_id": "x"})
