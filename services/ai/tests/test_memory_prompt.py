"""Tests du system_prompt memory_prompt (injection mémoire avec garde-fous)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.models.test import TestModel

from app.agent.tools import ToolContext, ToolDeps, build_agent
from app.i18n import t
from app.memory_stores import open_memory_store_for_scope
from app.sandbox.runner import SandboxRunner
from conftest import FakeProjectClient


def _memory_prompt_fn(agent):
    for runner in agent._system_prompt_functions:
        if runner.function.__name__ == "memory_prompt":
            return runner.function
    raise AssertionError("memory_prompt not registered on agent")


class _FakeRunContext:
    def __init__(
        self,
        workspace_data_dir: Path | None,
        *,
        locale: str = "fr",
        last_user_query: str = "",
    ) -> None:
        self.deps = ToolDeps(
            context=ToolContext(
                tenant_id="t",
                project_id="p",
                session_id="s",
                documents=[],
                workspace_data_dir=workspace_data_dir,
                locale=locale,
                last_user_query=last_user_query,
            ),
            project_client=FakeProjectClient(),
            sandbox_runner=SandboxRunner(timeout_seconds=10),
        )


def _workspace_dir(tmp_path: Path) -> Path:
    ws = tmp_path / "workspaces" / "ws1"
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def _seed_memory(scope: str, workspace_data_dir: Path, content: str) -> None:
    store = open_memory_store_for_scope(scope, workspace_data_dir)
    try:
        store.add_memory(content=content, source="manual")
    finally:
        store.close()


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_memory_prompt_empty_when_no_workspace(locale: str) -> None:
    agent = build_agent(TestModel(), locale=locale)
    prompt_fn = _memory_prompt_fn(agent)
    ctx = _FakeRunContext(None, locale=locale)

    assert prompt_fn(ctx) == ""


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_memory_prompt_empty_when_no_memories(
    locale: str,
    tmp_path: Path,
) -> None:
    agent = build_agent(TestModel(), locale=locale)
    prompt_fn = _memory_prompt_fn(agent)
    ctx = _FakeRunContext(_workspace_dir(tmp_path), locale=locale)

    assert prompt_fn(ctx) == ""


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_memory_prompt_user_scope_only(locale: str, tmp_path: Path) -> None:
    ws = _workspace_dir(tmp_path)
    _seed_memory("user", ws, "Préfère le français")

    agent = build_agent(TestModel(), locale=locale)
    prompt_fn = _memory_prompt_fn(agent)
    text = prompt_fn(_FakeRunContext(ws, locale=locale))

    assert t(locale, "memory.agent_guardrail") in text
    assert t(locale, "memory.untrusted_header") in text
    assert "<untrusted>" in text
    assert "</untrusted>" in text
    assert t(locale, "memory.agent_user_header") in text
    assert "Préfère le français" in text
    assert t(locale, "memory.agent_project_header") not in text
    assert text.count("<untrusted>") == 1


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_memory_prompt_project_scope_only(locale: str, tmp_path: Path) -> None:
    ws = _workspace_dir(tmp_path)
    _seed_memory("project", ws, "Dataset sur Kaggle")

    agent = build_agent(TestModel(), locale=locale)
    prompt_fn = _memory_prompt_fn(agent)
    text = prompt_fn(_FakeRunContext(ws, locale=locale))

    assert t(locale, "memory.agent_guardrail") in text
    assert t(locale, "memory.untrusted_header") in text
    assert "<untrusted>" in text
    assert t(locale, "memory.agent_project_header") in text
    assert "Dataset sur Kaggle" in text
    assert t(locale, "memory.agent_user_header") not in text
    assert text.count("<untrusted>") == 1


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_memory_prompt_both_scopes(locale: str, tmp_path: Path) -> None:
    ws = _workspace_dir(tmp_path)
    _seed_memory("user", ws, "Préfère le français")
    _seed_memory("project", ws, "Dataset sur Kaggle")

    agent = build_agent(TestModel(), locale=locale)
    prompt_fn = _memory_prompt_fn(agent)
    text = prompt_fn(_FakeRunContext(ws, locale=locale))

    assert t(locale, "memory.agent_guardrail") in text
    assert t(locale, "memory.untrusted_header") in text
    assert t(locale, "memory.agent_user_header") in text
    assert t(locale, "memory.agent_project_header") in text
    assert "Préfère le français" in text
    assert "Dataset sur Kaggle" in text
    assert text.count("<untrusted>") == 2
    assert text.count("</untrusted>") == 2


def test_memory_prompt_includes_query_relevant_fact_not_only_recent(
    tmp_path: Path,
) -> None:
    """Le ranking lexical injecte un fait pertinent même s'il n'est pas parmi les plus récents."""
    ws = _workspace_dir(tmp_path)
    facts = [
        "Alpha sans lien",
        "Beta sans lien",
        "Budget RH fixé à 120k€",
        "Gamma sans lien",
        "Delta sans lien",
        "Epsilon sans lien",
    ]
    for fact in facts:
        _seed_memory("project", ws, fact)

    agent = build_agent(TestModel(), locale="fr")
    prompt_fn = _memory_prompt_fn(agent)
    text = prompt_fn(
        _FakeRunContext(ws, locale="fr", last_user_query="budget RH annuel")
    )

    assert "Budget RH fixé à 120k€" in text
