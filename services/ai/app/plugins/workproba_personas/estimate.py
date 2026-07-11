"""Estimation de coût des sessions personas (P1 V9)."""

from __future__ import annotations

from typing import Any, Literal

from app.i18n import t
from app.plugins.workproba_personas import manifest, orchestrator

TOKENS_PER_CALL_INPUT = 2000
TOKENS_PER_CALL_OUTPUT = manifest.MAX_OPINION_TOKENS


def estimate_personas_cost(
    *,
    persona_ids: list[str],
    mode: Literal["ask", "meeting", "discuss"],
    rounds: int = manifest.DEFAULT_ROUNDS,
    settings_locked: bool = False,
    locale: str = "fr",
) -> dict[str, Any]:
    """Estime appels LLM et tokens avant lancement d'une session personas."""
    clamped_ids, persona_warnings = orchestrator.clamp_persona_ids(
        persona_ids, locale=locale
    )
    persona_count = len(clamped_ids)
    clamped_rounds = manifest.DEFAULT_ROUNDS
    round_warnings: list[str] = []

    if mode == "meeting":
        clamped_rounds, round_warnings = orchestrator.clamp_rounds(rounds, locale=locale)
        estimated_calls = persona_count * clamped_rounds + 1
    elif mode == "ask":
        estimated_calls = persona_count
    else:
        estimated_calls = persona_count

    estimated_tokens = estimated_calls * (TOKENS_PER_CALL_INPUT + TOKENS_PER_CALL_OUTPUT)

    warnings = persona_warnings + round_warnings
    warning: str | None = None
    if warnings:
        warning = " ".join(warnings)
    elif persona_count == 0:
        warning = t(locale, "personas.estimate.no_personas")
    elif settings_locked and (
        persona_count >= manifest.MAX_PERSONAS or clamped_rounds >= manifest.MAX_ROUNDS
    ):
        warning = t(locale, "personas.estimate.locked_cap")

    if warning is None and mode == "meeting":
        total_turns = persona_count * clamped_rounds
        if total_turns >= manifest.MAX_PERSONAS * manifest.MAX_ROUNDS:
            warning = t(
                locale,
                "personas.estimate.exceeds_cap",
                calls=estimated_calls,
                personas=persona_count,
            )

    return {
        "estimated_tokens": estimated_tokens,
        "estimated_calls": estimated_calls,
        "warning": warning,
        "persona_count": persona_count,
        "rounds": clamped_rounds if mode == "meeting" else None,
    }
