"""Outils agent du plugin personas."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ModelRetry

from app.agent.human import build_human_summary
from app.config import get_settings
from app.i18n import t
from app.plugins.registry import PLUGIN_WORKPROBA_PERSONAS, resolve_plugin_data_dir
from app.plugins.workproba_personas import manifest, orchestrator, storage
from app.plugins.workproba_personas.storage import JsonDict


def _plugin_data_dir(ctx: RunContext[Any]) -> Path:
    data_dir = resolve_plugin_data_dir(
        PLUGIN_WORKPROBA_PERSONAS,
        ctx.deps.context.plugin_data_dir,
    )
    if data_dir is None:
        raise ModelRetry("Plugin personas: plugin_data_dir manquant")
    return data_dir


def _persona_label(personas: list[JsonDict]) -> str:
    return ", ".join(str(p.get("name") or p.get("id") or "") for p in personas)


def register_personas_tools(agent: Agent[Any, str]) -> None:
    @agent.tool
    async def ask_personas(
        ctx: RunContext[Any],
        persona_ids: list[str],
        question: str,
        context: str = "",
    ) -> dict[str, Any]:
        """Ask one or more personas for their opinion on a topic.

        Returns structured opinions for inline display in the chat.

        Args:
            persona_ids: Persona identifiers (e.g. "01" for Sylvie).
            question: Subject or question for the personas.
            context: Optional extra context (document excerpt, draft, etc.).
        """
        locale = ctx.deps.context.locale
        plugin_data_dir = _plugin_data_dir(ctx)
        clamped_ids, _ = orchestrator.clamp_persona_ids(persona_ids, locale=locale)
        personas = storage.resolve_personas(plugin_data_dir, clamped_ids)
        if not personas:
            raise ModelRetry(t(locale, "errors.personas_not_found", ids=", ".join(persona_ids)))

        rag_store = getattr(ctx.deps.project_client, "_rag_store", None)
        try:
            opinions, warnings = await orchestrator.generate_opinions(
                plugin_data_dir=plugin_data_dir,
                persona_ids=clamped_ids,
                question=question,
                context=context,
                settings=get_settings(),
                provider_set=ctx.deps.context.provider_set,
                locale=locale,
                rag_store=rag_store,
            )
        except ValueError as exc:
            code = str(exc)
            detail = t(locale, f"errors.{code}")
            if detail == f"errors.{code}":
                detail = code
            raise ModelRetry(detail) from exc
        except Exception as exc:  # noqa: BLE001
            raise ModelRetry(f"{type(exc).__name__}: {exc}") from exc

        return {
            "opinions": opinions,
            "warnings": warnings,
            "display": "persona_opinion_card",
            "human_summary": build_human_summary(
                "ask_personas",
                {"names": _persona_label(personas), "question": question},
                result={"opinions": opinions},
                locale=locale,
            ),
        }

    @agent.tool
    async def simulate_meeting(
        ctx: RunContext[Any],
        persona_ids: list[str],
        topic: str,
        rounds: int = manifest.DEFAULT_ROUNDS,
    ) -> dict[str, Any]:
        """Start a simulated meeting between personas (dedicated full-screen view).

        The front opens the meeting view via the returned event metadata.

        Args:
            persona_ids: Participating persona identifiers.
            topic: Meeting subject.
            rounds: Number of discussion rounds (capped at 5).
        """
        locale = ctx.deps.context.locale
        plugin_data_dir = _plugin_data_dir(ctx)
        clamped_ids, persona_warnings = orchestrator.clamp_persona_ids(
            persona_ids, locale=locale
        )
        clamped_rounds, round_warnings = orchestrator.clamp_rounds(rounds, locale=locale)
        personas = storage.resolve_personas(plugin_data_dir, clamped_ids)
        if not personas:
            raise ModelRetry(t(locale, "errors.personas_not_found", ids=", ".join(persona_ids)))

        meeting_id = storage.new_meeting_id()
        names = _persona_label(personas)
        warnings = persona_warnings + round_warnings
        return {
            "action": "open_meeting_view",
            "meeting_id": meeting_id,
            "persona_ids": clamped_ids,
            "topic": topic,
            "rounds": clamped_rounds,
            "warnings": warnings,
            "human_summary": build_human_summary(
                "simulate_meeting",
                {"names": names, "topic": topic, "rounds": clamped_rounds},
                locale=locale,
            ),
        }
