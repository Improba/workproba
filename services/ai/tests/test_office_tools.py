"""Tests outils Office natifs (write_docx/xlsx/pdf)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.models.test import TestModel

from app.agent.tools import ToolDeps, build_agent
from app.documents.writer import build_docx_bytes, build_pdf_bytes, build_xlsx_bytes
from app.limits import DEFAULT_LIMITS
from app.sandbox.runner import SandboxRunner

from conftest import FakeProjectClient


def test_build_docx_bytes_contains_paragraphs() -> None:
    content = build_docx_bytes(title="Titre", paragraphs=["Ligne 1", "Ligne 2"])
    assert content.startswith(b"PK")
    assert len(content) > 100


def test_build_xlsx_bytes_contains_sheet() -> None:
    content = build_xlsx_bytes(
        sheets=[{"name": "Data", "rows": [["A", "B"], [1, 2]]}]
    )
    assert content.startswith(b"PK")


def test_build_pdf_bytes_produces_pdf() -> None:
    content = build_pdf_bytes(
        title="Rapport",
        sections=[{"heading": "Intro", "body": "Contenu"}],
    )
    assert content.startswith(b"%PDF")


def test_write_tools_registered() -> None:
    agent = build_agent(TestModel())
    names = sorted(agent._function_toolset.tools.keys())
    assert "write_docx" in names
    assert "write_xlsx" in names
    assert "write_pdf" in names


@pytest.mark.asyncio
async def test_write_docx_persists_file(tmp_path: Path) -> None:
    from pydantic_ai import RunContext

    client = FakeProjectClient()
    deps = ToolDeps(
        context=__import__("app.agent.tools", fromlist=["ToolContext"]).ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s",
            documents=[],
            project_root=tmp_path,
        ),
        project_client=client,
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
        confirmation_gate=None,
    )
    agent = build_agent(TestModel())
    tool = agent._function_toolset.tools["write_docx"]

    ctx = RunContext(deps=deps, model=TestModel(), usage=None, prompt=None, tool_call_id="tc1")
    result = await tool.function(ctx, path="out/report.docx", title="R", paragraphs=["Hi"])
    assert result.get("name") == "out/report.docx"
    assert client.saved
    assert client.saved[0]["mime_type"].endswith("document")
