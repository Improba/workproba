"""Traductions du plugin personas."""

from __future__ import annotations

from typing import Any

MESSAGES: dict[str, dict[str, Any]] = {
    "fr": {
        "human": {
            "ask_personas": {
                "will": "Je vais demander l'avis de {names}",
                "cannot": "Je n'ai pas pu obtenir l'avis des personas",
                "done": {
                    "one": "J'ai obtenu l'avis de {names}",
                    "many": "J'ai obtenu les avis de {names}",
                },
            },
            "simulate_meeting": {
                "will": "Je vais lancer une réunion avec {names} sur « {topic} »",
                "cannot": "Je n'ai pas pu lancer la réunion",
                "done": "J'ai lancé une réunion avec {names} ({rounds} tours)",
            },
        },
        "personas": {
            "rounds_capped": "Nombre de tours plafonné à {max}",
            "personas_capped": "Nombre de personas plafonné à {max}",
            "unknown_persona": "Persona inconnu : {id}",
            "no_personas": "Aucun persona sélectionné",
            "meeting_summary_title": "Synthèse de Nathalie",
            "animator_label": "Animateur",
            "memory_context_header": "Extraits de la mémoire de l'espace :",
            "meeting": {
                "facilitator": {
                    "round1": "Tour 1 — avis initial",
                    "round_n": "Tour {n} — réactions",
                    "synthesis": "Synthèse",
                },
            },
        },
        "plugin": {
            "workproba": {
                "personas": {
                    "name": "Personas",
                    "ask_action": "Demander l'avis",
                    "meeting_action": "Simuler une réunion",
                    "discuss_action": "Discuter avec",
                },
            },
        },
        "errors": {
            "personas_not_found": "Personas introuvables : {ids}",
            "rounds_exceed_max": "Nombre de tours trop élevé (max {max})",
            "personas_exceed_max": "Trop de personas sélectionnés (max {max})",
        },
    },
    "en": {
        "human": {
            "ask_personas": {
                "will": "I will ask {names} for their opinion",
                "cannot": "I could not get personas' opinions",
                "done": {
                    "one": "I got an opinion from {names}",
                    "many": "I got opinions from {names}",
                },
            },
            "simulate_meeting": {
                "will": "I will start a meeting with {names} about « {topic} »",
                "cannot": "I could not start the meeting",
                "done": "I started a meeting with {names} ({rounds} rounds)",
            },
        },
        "personas": {
            "rounds_capped": "Round count capped at {max}",
            "personas_capped": "Persona count capped at {max}",
            "unknown_persona": "Unknown persona: {id}",
            "no_personas": "No persona selected",
            "meeting_summary_title": "Nathalie's summary",
            "animator_label": "Facilitator",
            "memory_context_header": "Excerpts from workspace memory:",
            "meeting": {
                "facilitator": {
                    "round1": "Round 1 — initial views",
                    "round_n": "Round {n} — reactions",
                    "synthesis": "Summary",
                },
            },
        },
        "plugin": {
            "workproba": {
                "personas": {
                    "name": "Personas",
                    "ask_action": "Ask for opinion",
                    "meeting_action": "Simulate a meeting",
                    "discuss_action": "Discuss with",
                },
            },
        },
        "errors": {
            "personas_not_found": "Personas not found: {ids}",
            "rounds_exceed_max": "Too many rounds (max {max})",
            "personas_exceed_max": "Too many personas selected (max {max})",
        },
    },
}
