"""Tests du prompt dynamique space_name_prompt."""

from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel

from app.agent.tools import ToolContext, ToolDeps, build_agent
from app.i18n import t
from app.sandbox.runner import SandboxRunner
from conftest import FakeProjectClient


def _space_name_prompt_fn(agent):
    for runner in agent._system_prompt_functions:
        if runner.function.__name__ == "space_name_prompt":
            return runner.function
    raise AssertionError("space_name_prompt not registered on agent")


class _FakeRunContext:
    def __init__(self, workspace_title: str | None, locale: str = "fr") -> None:
        self.deps = ToolDeps(
            context=ToolContext(
                tenant_id="t",
                project_id="p",
                session_id="s",
                documents=[],
                workspace_title=workspace_title,
                locale=locale,
            ),
            project_client=FakeProjectClient(),
            sandbox_runner=SandboxRunner(timeout_seconds=10),
        )


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_space_name_prompt_injects_title(locale: str) -> None:
    agent = build_agent(TestModel(), locale=locale)
    prompt_fn = _space_name_prompt_fn(agent)
    ctx = _FakeRunContext("kaggle", locale=locale)

    text = prompt_fn(ctx)

    assert "kaggle" in text
    assert text == t(locale, "tools.space_name_context", name="kaggle")


@pytest.mark.parametrize("locale", ["fr", "en"])
@pytest.mark.parametrize("title", [None, "", "   "])
def test_space_name_prompt_empty_when_no_title(
    locale: str,
    title: str | None,
) -> None:
    agent = build_agent(TestModel(), locale=locale)
    prompt_fn = _space_name_prompt_fn(agent)
    ctx = _FakeRunContext(title, locale=locale)

    assert prompt_fn(ctx) == ""


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_space_name_prompt_wording_trusts_user_override(locale: str) -> None:
    """Le wording reste respectueux d'un changement d'espace signalé par l'utilisateur.

    On fige la formulation pour éviter une régression vers une interdiction trop
    absolue (« jamais ») qui contredirait l'utilisateur s'il change d'espace.
    """
    agent = build_agent(TestModel(), locale=locale)
    prompt_fn = _space_name_prompt_fn(agent)
    ctx = _FakeRunContext("kaggle", locale=locale)

    text = prompt_fn(ctx)

    if locale == "fr":
        assert "plutôt qu'un nom d'espace lu" in text
        assert "fais confiance à l'utilisateur" in text
        assert "jamais" not in text
    else:
        assert "rather than a workspace name read from" in text
        assert "trust the user" in text
        assert " never " not in text
