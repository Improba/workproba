"""Tests plugin projet (storage, outils, sécurité)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.models.test import TestModel

from app.agent.confirmation import APPROVAL_DENIED_MARKER, ConfirmationGate
from app.agent.human import build_human_summary
from app.agent.tools import ToolDeps, ToolContext, build_agent
from app.limits import DEFAULT_LIMITS
from app.plugins.workproba_projet import PLUGIN_ID
from app.plugins.workproba_projet import storage
from app.sandbox.runner import SandboxRunner

from conftest import FakeProjectClient


@pytest.fixture
def plugin_dir(tmp_path: Path) -> Path:
    path = tmp_path / "plugins" / "workproba.projet"
    path.mkdir(parents=True)
    return path


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "rapport.docx").write_bytes(b"PK fake docx")
    return ws


def test_create_and_list_projects(plugin_dir: Path) -> None:
    project = storage.create_project(plugin_dir, "Contrat RH")
    projects = storage.load_projects(plugin_dir)
    assert len(projects) == 1
    assert projects[0]["id"] == project["id"]
    assert projects[0]["name"] == "Contrat RH"
    assert "created_at" in projects[0]


def test_publish_artifact_copies_file(plugin_dir: Path, workspace: Path) -> None:
    project = storage.create_project(plugin_dir, "Alpha")
    artefact = storage.publish_artifact(
        plugin_data_dir=plugin_dir,
        workspace_root=workspace,
        source_path="rapport.docx",
        project_id=project["id"],
        name="rapport.docx",
    )
    dest = plugin_dir / "artefacts" / project["id"] / "rapport.docx"
    assert dest.is_file()
    assert artefact["name"] == "rapport.docx"
    assert artefact["project_name"] == "Alpha"


def test_publish_artifact_writes_markdown_content(plugin_dir: Path) -> None:
    project = storage.create_project(plugin_dir, "Alpha")
    markdown = "# Réunion personas\n\nSynthèse de la discussion."
    artefact = storage.publish_artifact(
        plugin_data_dir=plugin_dir,
        content=markdown,
        project_id=project["id"],
        name="reunion-transcript",
    )
    dest = plugin_dir / "artefacts" / project["id"] / "reunion-transcript.md"
    assert dest.is_file()
    assert dest.read_text(encoding="utf-8") == markdown
    assert artefact["name"] == "reunion-transcript.md"
    assert artefact.get("source_path") is None


def test_publish_artifact_content_rejects_oversized(plugin_dir: Path) -> None:
    project = storage.create_project(plugin_dir, "Alpha")
    huge = "x" * (storage.MAX_PUBLISH_CONTENT_BYTES + 1)
    with pytest.raises(ValueError, match="content_too_large"):
        storage.publish_artifact(
            plugin_data_dir=plugin_dir,
            content=huge,
            project_id=project["id"],
            name="big.md",
        )


def test_publish_artifact_content_name_path_traversal(plugin_dir: Path) -> None:
    project = storage.create_project(plugin_dir, "Alpha")
    artefact = storage.publish_artifact(
        plugin_data_dir=plugin_dir,
        content="# ok",
        project_id=project["id"],
        name="../../evil.md",
    )
    dest = plugin_dir / "artefacts" / project["id"] / "evil.md"
    assert dest.is_file()
    assert artefact["name"] == "evil.md"


def test_publish_artifact_path_traversal(plugin_dir: Path, workspace: Path) -> None:
    project = storage.create_project(plugin_dir, "Alpha")
    with pytest.raises(ValueError, match="path_outside_workspace"):
        storage.publish_artifact(
            plugin_data_dir=plugin_dir,
            workspace_root=workspace,
            source_path="../outside.txt",
            project_id=project["id"],
            name="evil.txt",
        )


def test_publish_artifact_unknown_project(plugin_dir: Path, workspace: Path) -> None:
    with pytest.raises(ValueError, match="project_not_found"):
        storage.publish_artifact(
            plugin_data_dir=plugin_dir,
            workspace_root=workspace,
            source_path="rapport.docx",
            project_id="missing",
            name="rapport.docx",
        )


def test_plugin_tools_hidden_without_active_plugins() -> None:
    agent = build_agent(TestModel())
    names = sorted(agent._function_toolset.tools.keys())
    assert "publish_artifact" not in names
    assert "list_projects" not in names
    assert "create_project" not in names


def test_plugin_tools_registered_when_active() -> None:
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_ID])
    names = sorted(agent._function_toolset.tools.keys())
    assert "publish_artifact" in names
    assert "list_projects" in names
    assert "create_project" in names


@pytest.mark.asyncio
async def test_publish_artifact_requires_confirmation(
    plugin_dir: Path,
    workspace: Path,
) -> None:
    project = storage.create_project(plugin_dir, "Beta")
    gate = ConfirmationGate(session_id="s1", turn_id="t1")
    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s1",
            documents=[],
            project_root=workspace,
            plugin_data_dir=plugin_dir,
            locale="fr",
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
        confirmation_gate=gate,
    )
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_ID])
    tool = agent._function_toolset.tools["publish_artifact"]
    ctx = RunContext(deps=deps, model=TestModel(), usage=None, prompt=None, tool_call_id="tc1")

    async def deny_later() -> None:
        await asyncio.sleep(0.05)
        for cid in list(gate._pending):
            gate.resolve(cid, "deny")

    asyncio.create_task(deny_later())
    with pytest.raises(ModelRetry) as exc_info:
        await tool.function(
            ctx,
            project_id=project["id"],
            name="rapport.docx",
            source_path="rapport.docx",
        )
    assert APPROVAL_DENIED_MARKER in str(exc_info.value)


@pytest.mark.asyncio
async def test_publish_artifact_with_approval(
    plugin_dir: Path,
    workspace: Path,
) -> None:
    project = storage.create_project(plugin_dir, "Gamma")
    gate = ConfirmationGate(session_id="s1", turn_id="t1")
    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s1",
            documents=[],
            project_root=workspace,
            plugin_data_dir=plugin_dir,
            locale="fr",
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
        confirmation_gate=gate,
    )
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_ID])
    tool = agent._function_toolset.tools["publish_artifact"]
    ctx = RunContext(deps=deps, model=TestModel(), usage=None, prompt=None, tool_call_id="tc1")

    async def approve_later() -> None:
        await asyncio.sleep(0.05)
        for cid in list(gate._pending):
            gate.resolve(cid, "approve")

    asyncio.create_task(approve_later())
    result = await tool.function(
        ctx,
        project_id=project["id"],
        name="rapport.docx",
        source_path="rapport.docx",
    )
    assert result.get("name") == "rapport.docx"
    assert result.get("project_name") == "Gamma"


def test_human_summary_publish_artifact_fr() -> None:
    summary = build_human_summary(
        "publish_artifact",
        {"name": "doc.pdf", "project": "Alpha"},
        result={"project_name": "Alpha", "name": "doc.pdf"},
        locale="fr",
    )
    assert "doc.pdf" in summary
    assert "Alpha" in summary
