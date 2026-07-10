"""Tests de durcissement des outils Workproba.

Couvrent les protections ajoutées :
- read_document : plafond lignes/octet + pagination + métadonnées de troncature.
- LocalExtractor : plafond caractères sur docx.
- search_kb : clamp du `limit`.
- generate_document : denylist (.env/.git) + pas d'écho du contenu + plafond taille.
- SandboxRunner : exécution réelle, exit_code, plafond de sortie, fichiers
  projet exposés, env sanitized, écritures isolées.
"""

from __future__ import annotations

import asyncio
import base64
from io import BytesIO
from pathlib import Path

import pytest

from app.documents.extractor import LocalExtractor
from app.limits import Limits
from app.local_client import LocalProjectClient
from app.sandbox.runner import SandboxRunner


# --- read_document ---------------------------------------------------------


def _write_lines(path: Path, n: int, prefix: str = "ligne") -> None:
    path.write_text("\n".join(f"{prefix}-{i:05d}" for i in range(n)), encoding="utf-8")


def test_read_document_truncation_by_lines(tmp_path: Path) -> None:
    _write_lines(tmp_path / "big.txt", 5000)
    client = LocalProjectClient(project_root=tmp_path, limits=Limits(read_max_lines=2000))

    doc = asyncio.run(
        client.read_document(
            tenant_id="t", project_id="p", document_id="big.txt"
        )
    )
    assert doc.metadata["truncated"] is True
    assert doc.metadata["truncation_reason"] == "max_lines"
    assert doc.metadata["lines_returned"] == 2000
    assert doc.metadata["size_bytes"] > doc.metadata["bytes_returned"]


def test_read_document_pagination(tmp_path: Path) -> None:
    _write_lines(tmp_path / "big.txt", 5000)
    client = LocalProjectClient(project_root=tmp_path, limits=Limits(read_max_lines=2000))

    first = asyncio.run(
        client.read_document(tenant_id="t", project_id="p", document_id="big.txt")
    )
    second = asyncio.run(
        client.read_document(
            tenant_id="t",
            project_id="p",
            document_id="big.txt",
            offset_lines=2000,
        )
    )
    assert first.text.splitlines()[0] == "ligne-00000"
    assert second.text.splitlines()[0] == "ligne-02000"
    assert first.text != second.text


def test_read_document_truncation_by_bytes(tmp_path: Path) -> None:
    _write_lines(tmp_path / "big.txt", 5000)
    client = LocalProjectClient(
        project_root=tmp_path, limits=Limits(read_max_lines=100_000, read_max_bytes=150)
    )

    doc = asyncio.run(
        client.read_document(tenant_id="t", project_id="p", document_id="big.txt")
    )
    assert doc.metadata["truncated"] is True
    assert doc.metadata["truncation_reason"] == "max_bytes"
    assert doc.metadata["bytes_returned"] <= 150


def test_read_document_full_when_small(tmp_path: Path) -> None:
    (tmp_path / "small.txt").write_text("coucou\n", encoding="utf-8")
    client = LocalProjectClient(project_root=tmp_path)

    doc = asyncio.run(
        client.read_document(tenant_id="t", project_id="p", document_id="small.txt")
    )
    assert doc.text == "coucou\n"
    assert doc.metadata["truncated"] is False
    assert doc.metadata["lines_returned"] == 1


def test_read_document_binary_size_guard(tmp_path: Path) -> None:
    # Un faux PDF (contenu non parsé) : on garde avant l'extraction grâce au
    # plafond extract_max_input_bytes.
    (tmp_path / "huge.pdf").write_bytes(b"%PDF-1.4 " + b"x" * 2048)
    client = LocalProjectClient(
        project_root=tmp_path, limits=Limits(extract_max_input_bytes=128)
    )
    with pytest.raises(ValueError, match="trop volumineux"):
        asyncio.run(
            client.read_document(tenant_id="t", project_id="p", document_id="huge.pdf")
        )


# --- extractor -------------------------------------------------------------


def test_extract_docx_truncation_by_chars() -> None:
    from docx import Document

    doc = Document()
    for i in range(500):
        doc.add_paragraph(f"Paragraphe numero {i} " + "x" * 200)
    buf = BytesIO()
    doc.save(buf)

    extractor = LocalExtractor(limits=Limits(extract_max_chars=300))
    result = asyncio.run(
        extractor.extract(content=buf.getvalue(), filename="note.docx", mime_type=None)
    )
    assert result.metadata["truncated"] is True
    assert result.metadata["chars_total"] > 300
    assert len(result.text) <= 300


# --- search_kb -------------------------------------------------------------


def test_search_kb_limit_clamped(tmp_path: Path) -> None:
    for i in range(30):
        (tmp_path / f"f{i}.txt").write_text(f"match contenu {i}", encoding="utf-8")
    client = LocalProjectClient(
        project_root=tmp_path, limits=Limits(search_max_limit=5, search_file_max_bytes=1_000_000)
    )

    response = asyncio.run(
        client.search_kb(tenant_id="t", project_id="p", query="match", limit=10_000)
    )
    assert len(response.results) <= 5


# --- generate_document -----------------------------------------------------


def test_generate_document_denylist_env(tmp_path: Path) -> None:
    client = LocalProjectClient(project_root=tmp_path)
    payload = base64.b64encode(b"SECRET=1").decode("ascii")
    with pytest.raises(ValueError, match="not allowed"):
        asyncio.run(
            client.save_generated_document(
                tenant_id="t",
                project_id="p",
                session_id="sess",
                name=".env",
                mime_type="text/plain",
                content_base64=payload,
            )
        )


def test_generate_document_denylist_git(tmp_path: Path) -> None:
    client = LocalProjectClient(project_root=tmp_path)
    payload = base64.b64encode(b"[remote]").decode("ascii")
    with pytest.raises(ValueError, match="not allowed"):
        asyncio.run(
            client.save_generated_document(
                tenant_id="t",
                project_id="p",
                session_id="sess",
                name=".git/config",
                mime_type="text/plain",
                content_base64=payload,
            )
        )


def test_generate_document_no_echo_and_saved(tmp_path: Path) -> None:
    client = LocalProjectClient(project_root=tmp_path)
    payload = base64.b64encode(b"# Rapport\n\ndu contenu").decode("ascii")
    doc = asyncio.run(
        client.save_generated_document(
            tenant_id="t",
            project_id="p",
            session_id="sess",
            name="rapport.md",
            mime_type="text/markdown",
            content_base64=payload,
        )
    )
    assert doc.text is None
    assert doc.metadata["saved"] is True
    assert doc.metadata["size_bytes"] == len(b"# Rapport\n\ndu contenu")
    assert (tmp_path / "rapport.md").read_bytes() == b"# Rapport\n\ndu contenu"


def test_generate_document_size_cap(tmp_path: Path) -> None:
    client = LocalProjectClient(
        project_root=tmp_path, limits=Limits(generate_max_bytes=128)
    )
    big = b"x" * 1024
    payload = base64.b64encode(big).decode("ascii")
    with pytest.raises(ValueError, match="too large"):
        asyncio.run(
            client.save_generated_document(
                tenant_id="t",
                project_id="p",
                session_id="sess",
                name="big.bin",
                mime_type="application/octet-stream",
                content_base64=payload,
            )
        )


# --- SandboxRunner ---------------------------------------------------------


def _runner(*, timeout: int = 15, limits: Limits | None = None) -> SandboxRunner:
    return SandboxRunner(timeout_seconds=timeout, limits=limits or Limits())


def test_sandbox_exit_code(tmp_path: Path) -> None:
    result = asyncio.run(
        _runner().run(code="import sys; sys.exit(7)", project_files=[], project_root=tmp_path)
    )
    assert result.metadata["exit_code"] == 7
    assert result.metadata["isolation"] in {"bwrap", "resource-limits", "none"}


def test_sandbox_output_capped(tmp_path: Path) -> None:
    limits = Limits(sandbox_output_max_bytes=1024, sandbox_memory_mb=512)
    code = 'import sys; sys.stdout.write("x" * (5 * 1024 * 1024))'
    result = asyncio.run(_runner(limits=limits).run(code=code, project_files=[], project_root=tmp_path))
    assert result.metadata["stdout_truncated"] is True
    assert len(result.stdout) <= 1024


def test_sandbox_project_files_exposed(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_text("hello-xyz-123", encoding="utf-8")
    code = 'print(open("data.txt").read())'
    result = asyncio.run(
        _runner().run(code=code, project_files=["data.txt"], project_root=tmp_path)
    )
    assert "hello-xyz-123" in result.stdout
    assert result.metadata["project_files_copied"] == 1


def test_sandbox_env_sanitized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WP_LEAK_SECRET", "supersecret-token")
    code = 'import os; print(os.environ.get("WP_LEAK_SECRET", "NONE"))'
    result = asyncio.run(_runner().run(code=code, project_files=[], project_root=tmp_path))
    assert "supersecret-token" not in result.stdout
    assert "NONE" in result.stdout


def test_sandbox_writes_isolated_and_collected(tmp_path: Path) -> None:
    code = 'open("out.txt", "w").write("generated-content")'
    result = asyncio.run(_runner().run(code=code, project_files=[], project_root=tmp_path))
    # Le fichier est écrit dans le tmpdir jetable, pas dans le projet réel.
    assert not (tmp_path / "out.txt").exists()
    # Il est collecté et renvoyé à l'agent.
    files = [f for f in result.files if f.path == "out.txt"]
    assert files, "generated file should be collected"
    assert base64.b64decode(files[0].content_base64 or "") == b"generated-content"


def test_sandbox_timeout(tmp_path: Path) -> None:
    runner = SandboxRunner(timeout_seconds=1, limits=Limits())
    result = asyncio.run(
        runner.run(code="import time; time.sleep(10)", project_files=[], project_root=tmp_path)
    )
    assert result.timed_out is True
    assert "timeout" in result.stderr.lower()


# --- list_files + inventaire ----------------------------------------------


def _make_tree(root: Path) -> None:
    (root / "assets").mkdir()
    (root / "assets" / "index.html").write_text("<html></html>", encoding="utf-8")
    (root / "assets" / "terraform.zip").write_bytes(b"PK\x03\x04")
    (root / "README.md").write_text("# demo", encoding="utf-8")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("git", encoding="utf-8")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "x.js").write_text("module.exports=1", encoding="utf-8")


def test_list_files_basic(tmp_path: Path) -> None:
    _make_tree(tmp_path)
    client = LocalProjectClient(project_root=tmp_path)

    response = asyncio.run(client.list_files())
    paths = {entry.path for entry in response.entries}
    assert "assets" in paths
    assert "assets/index.html" in paths
    assert "assets/terraform.zip" in paths
    assert "README.md" in paths
    assets_entry = next(e for e in response.entries if e.path == "assets")
    assert assets_entry.is_dir is True
    assert assets_entry.kind == "folder"
    html_entry = next(e for e in response.entries if e.path == "assets/index.html")
    assert html_entry.kind == "html"
    assert html_entry.size_bytes > 0


def test_list_files_ignores_sensitive_dirs(tmp_path: Path) -> None:
    _make_tree(tmp_path)
    client = LocalProjectClient(project_root=tmp_path)

    response = asyncio.run(client.list_files())
    paths = {entry.path for entry in response.entries}
    assert not any(p.startswith(".git") for p in paths)
    assert not any(p.startswith("node_modules") for p in paths)


def test_list_files_truncation(tmp_path: Path) -> None:
    for i in range(10):
        (tmp_path / f"f{i}.txt").write_text("x", encoding="utf-8")
    client = LocalProjectClient(project_root=tmp_path, limits=Limits(list_max_entries=3))

    response = asyncio.run(client.list_files())
    assert response.truncated is True
    assert response.truncation_reason == "max_entries"
    assert len(response.entries) == 3


def test_list_files_subdir_escape_rejected(tmp_path: Path) -> None:
    _make_tree(tmp_path)
    client = LocalProjectClient(project_root=tmp_path)
    with pytest.raises(ValueError, match="escapes project root"):
        asyncio.run(client.list_files(subdir="../"))


def test_list_files_subdir_filter(tmp_path: Path) -> None:
    _make_tree(tmp_path)
    client = LocalProjectClient(project_root=tmp_path)

    response = asyncio.run(client.list_files(subdir="assets"))
    paths = {entry.path for entry in response.entries}
    assert paths == {"assets/index.html", "assets/terraform.zip"}


def test_inventory_prompt_lists_files() -> None:
    from app.agent.tools import build_inventory_prompt
    from app.schemas import DocumentReference

    docs = [
        DocumentReference(
            id="assets/index.html",
            name="index.html",
            metadata={"relativePath": "assets/index.html", "kind": "html"},
        ),
        DocumentReference(
            id="assets/terraform.zip",
            name="terraform.zip",
            metadata={"relativePath": "assets/terraform.zip", "kind": "file"},
        ),
    ]
    prompt = build_inventory_prompt(docs, cap=200)
    assert "assets/index.html" in prompt
    assert "assets/terraform.zip" in prompt
    assert "list_files" in prompt


def test_inventory_prompt_empty_advises_list_files() -> None:
    from app.agent.tools import build_inventory_prompt

    prompt = build_inventory_prompt([], cap=200)
    assert "list_files" in prompt
    assert "vide" in prompt


def test_inventory_prompt_truncates_with_overflow_notice() -> None:
    from app.agent.tools import build_inventory_prompt
    from app.schemas import DocumentReference

    docs = [
        DocumentReference(id=f"f{i}.txt", name=f"f{i}.txt", metadata={"relativePath": f"f{i}.txt"})
        for i in range(10)
    ]
    prompt = build_inventory_prompt(docs, cap=3)
    assert "f0.txt" in prompt
    assert "f9.txt" not in prompt
    assert "7 autres fichiers" in prompt

