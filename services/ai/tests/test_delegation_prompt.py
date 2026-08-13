"""Tests du prompt de délégation agents métier."""

from __future__ import annotations

from app.plugins.workproba_personas.delegation_prompt import (
    build_business_agents_delegation_prompt,
)


def _sample_rh_specialist() -> dict[str, object]:
    return {
        "id": "org.gestionnaire",
        "name": "Gestionnaire",
        "role": "RH",
        "description": "Gestion RH et saisie de temps Ihora.",
        "tools": {
            "allowed": [
                {"connector_id": "ihora", "tool": "list_absences"},
                {"connector_id": "ihora", "tool": "create_timesheet"},
            ],
            "forbidden": [],
        },
    }


def test_build_business_agents_delegation_prompt_lists_specialist() -> None:
    text = build_business_agents_delegation_prompt("fr", [_sample_rh_specialist()])
    assert "org.gestionnaire" in text
    assert "Gestionnaire" in text
    assert "ihora" in text
    assert "summon_specialist" in text
    assert "regard" in text
    assert "operative" in text
    assert "managed_*" in text
    assert "ask_personas" in text
    assert "verbatim" in text.lower() or "reformulez" in text.lower()


def test_build_business_agents_delegation_prompt_empty() -> None:
    fr_text = build_business_agents_delegation_prompt("fr", [])
    en_text = build_business_agents_delegation_prompt("en", [])
    assert fr_text
    assert en_text
    assert "summon_specialist" in fr_text
    assert "synchroniser" in fr_text.lower()
    assert "sync" in en_text.lower()


def test_build_business_agents_delegation_prompt_uses_doctrine_mission() -> None:
    specialist = {
        "id": "org.gestionnaire",
        "name": "Gestionnaire",
        "doctrine": {"mission": "Piloter la saisie de temps et les absences."},
        "tools": {"allowed": [{"connector_id": "ihora", "tool": "list_users"}]},
    }
    text = build_business_agents_delegation_prompt("en", [specialist])
    assert "Piloter la saisie de temps" in text


def test_build_business_agents_delegation_prompt_includes_no_ritual_rule() -> None:
    text = build_business_agents_delegation_prompt("fr", [_sample_rh_specialist()])
    assert "CONFIRMATION DIRECTE" in text or "Je suis" in text
    assert "Human Approval Gate" in text or "carte Human Approval Gate" in text
    assert "rôle gestionnaire iHora" in text or "gestionnaire iHora" in text
