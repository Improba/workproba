"""Tests du manifest prompt (refs, empreintes, stabilité)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic_ai.models.test import TestModel

from app.agent.tools import ToolContext, ToolDeps, build_agent
from app.i18n import t
from app.memory_stores import open_memory_store_for_scope
from app.prompts.manifest import collect_prompt_manifest
from app.prompts.registry import (
    PROMPT_SPECS,
    combined_sha256,
    prompt_ref,
    redact_model_settings,
    template_sha256,
)
from app.sandbox.runner import SandboxRunner
from conftest import FakeProjectClient


class _FakeRunContext:
    def __init__(
        self,
        *,
        workspace_data_dir: Path | None = None,
        locale: str = "fr",
        documents: list | None = None,
        workspace_title: str | None = None,
        last_user_query: str = "",
        active_plugins: list[str] | None = None,
        plugin_data_dir: Path | None = None,
    ) -> None:
        self.deps = ToolDeps(
            context=ToolContext(
                tenant_id="t",
                project_id="p",
                session_id="s",
                documents=documents or [],
                workspace_data_dir=workspace_data_dir,
                workspace_title=workspace_title,
                locale=locale,
                active_plugins=active_plugins,
                plugin_data_dir=plugin_data_dir,
                last_user_query=last_user_query,
            ),
            project_client=FakeProjectClient(),
            sandbox_runner=SandboxRunner(timeout_seconds=10),
        )


def _workspace_dir(tmp_path: Path) -> Path:
    ws = tmp_path / "workspaces" / "ws1"
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def test_prompt_ref_versioning() -> None:
    assert prompt_ref("tools.system_prompt") == "tools.system_prompt@1"
    assert prompt_ref("dynamic:memory@2", version=1) == "dynamic:memory@2"


def test_template_sha256_stable_per_locale() -> None:
    fr_hash = template_sha256("fr", "tools.system_prompt")
    en_hash = template_sha256("en", "tools.system_prompt")
    assert fr_hash != en_hash
    assert template_sha256("fr", "tools.system_prompt") == fr_hash


def test_sessions_note_hashes_with_neutral_placeholder() -> None:
    digest = template_sha256("fr", "tools.sessions_note", count=0)
    expected = template_sha256("fr", "tools.sessions_note", **PROMPT_SPECS["tools.sessions_note"])
    assert digest == expected


def test_redact_model_settings_strips_secrets() -> None:
    redacted = redact_model_settings(
        {
            "temperature": 0.2,
            "api_key": "secret-key",
            "extra_headers": {"Authorization": "Bearer tok", "X-Trace": "1"},
            "nested": {"client_secret": "abc"},
        }
    )
    assert redacted["temperature"] == 0.2
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["extra_headers"]["Authorization"] == "[REDACTED]"
    assert redacted["extra_headers"]["X-Trace"] == "1"
    assert redacted["nested"]["client_secret"] == "[REDACTED]"


def test_collect_prompt_manifest_static_and_dynamic_refs() -> None:
    agent = build_agent(TestModel(), locale="fr")
    deps = _FakeRunContext(workspace_title="Mon espace").deps
    manifest = collect_prompt_manifest(agent, deps)

    refs = {entry["ref"] for entry in manifest["prompt_refs"]}
    assert prompt_ref("tools.system_prompt") in refs
    assert prompt_ref("dynamic:space_name") in refs
    assert prompt_ref("dynamic:memory") in refs
    assert manifest["combined_sha256"]
    assert manifest["variables"]["workspace_title"] == "Mon espace"
    assert manifest["variables"]["personas_active"] is False


def test_collect_prompt_manifest_identical_hashes_on_consecutive_runs(
    tmp_path: Path,
) -> None:
    ws = _workspace_dir(tmp_path)
    store = open_memory_store_for_scope("project", ws)
    try:
        store.add_memory(content="fait durable", source="user")
    finally:
        store.close()

    agent = build_agent(TestModel(), locale="fr")
    deps = _FakeRunContext(
        workspace_data_dir=ws,
        workspace_title="kaggle",
        last_user_query="rappelle le dataset",
    ).deps

    first = collect_prompt_manifest(agent, deps)
    second = collect_prompt_manifest(agent, deps)

    assert first["combined_sha256"] == second["combined_sha256"]
    assert first["prompt_refs"] == second["prompt_refs"]


def test_collect_prompt_manifest_no_full_prompt_text(tmp_path: Path) -> None:
    ws = _workspace_dir(tmp_path)
    store = open_memory_store_for_scope("project", ws)
    try:
        store.add_memory(content="souvenir très secret", source="user")
    finally:
        store.close()

    agent = build_agent(TestModel(), locale="fr")
    deps = _FakeRunContext(workspace_data_dir=ws, last_user_query="hello").deps
    manifest = collect_prompt_manifest(agent, deps)
    serialized = json.dumps(manifest)

    assert "souvenir très secret" not in serialized
    assert t("fr", "tools.system_prompt") not in serialized


def test_combined_sha256_order_independent_of_insertion() -> None:
    pairs_a = [("b@1", "hash-b"), ("a@1", "hash-a")]
    pairs_b = [("a@1", "hash-a"), ("b@1", "hash-b")]
    assert combined_sha256(pairs_a) == combined_sha256(pairs_b)
