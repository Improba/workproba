"""Traductions du plugin browser."""

from __future__ import annotations

from typing import Any

MESSAGES: dict[str, dict[str, Any]] = {
    "fr": {
        "human": {
            "browser_navigate": {
                "will": "Je vais ouvrir {url}",
                "cannot": "Je n'ai pas pu ouvrir la page",
                "done": "J'ai ouvert {url}",
            },
            "browser_click": {
                "will": "Je vais cliquer sur l'élément {ref}",
                "cannot": "Je n'ai pas pu cliquer sur l'élément",
                "done": "J'ai cliqué sur l'élément {ref}",
            },
            "browser_extract": {
                "will": "Je vais extraire le contenu de {selector}",
                "cannot": "Je n'ai pas pu extraire le contenu",
                "done": "J'ai extrait le contenu de {selector}",
            },
        },
        "plugin": {
            "workproba": {
                "browser": {
                    "name": "Browser",
                },
            },
        },
        "errors": {
            "browser_not_available": "Le navigateur intégré n'est pas disponible",
            "browser_url_scheme_forbidden": "Schéma d'URL non autorisé (http/https uniquement)",
            "browser_url_invalid": "URL invalide",
            "browser_session_inactive": "Aucune session browser active",
            "browser_action_timeout": "L'action browser a expiré",
            "browser_locked": "Navigateur interdit en mode verrouillé",
            "browser_ref_missing": "Référence d'élément manquante",
            "browser_selector_missing": "Sélecteur CSS manquant",
        },
    },
    "en": {
        "human": {
            "browser_navigate": {
                "will": "I will open {url}",
                "cannot": "I could not open the page",
                "done": "I opened {url}",
            },
            "browser_click": {
                "will": "I will click element {ref}",
                "cannot": "I could not click the element",
                "done": "I clicked element {ref}",
            },
            "browser_extract": {
                "will": "I will extract content from {selector}",
                "cannot": "I could not extract the content",
                "done": "I extracted content from {selector}",
            },
        },
        "plugin": {
            "workproba": {
                "browser": {
                    "name": "Browser",
                },
            },
        },
        "errors": {
            "browser_not_available": "Embedded browser is not available",
            "browser_url_scheme_forbidden": "URL scheme not allowed (http/https only)",
            "browser_url_invalid": "Invalid URL",
            "browser_session_inactive": "No active browser session",
            "browser_action_timeout": "Browser action timed out",
            "browser_locked": "Browser is forbidden in locked mode",
            "browser_ref_missing": "Element reference is required",
            "browser_selector_missing": "CSS selector is required",
        },
    },
}
