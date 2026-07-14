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
            "browser_type": {
                "will": "Je vais saisir du texte dans l'élément {ref}",
                "cannot": "Je n'ai pas pu saisir le texte",
                "done": "J'ai saisi du texte dans l'élément {ref}",
            },
            "browser_scroll": {
                "will": "Je vais faire défiler la page vers {direction}",
                "cannot": "Je n'ai pas pu faire défiler la page",
                "done": "J'ai fait défiler la page vers {direction}",
            },
            "browser_press": {
                "will": "Je vais appuyer sur la touche {press_key}",
                "cannot": "Je n'ai pas pu appuyer sur la touche",
                "done": "J'ai appuyé sur la touche {press_key}",
            },
            "browser_back": {
                "will": "Je vais revenir à la page précédente",
                "cannot": "Je n'ai pas pu revenir en arrière",
                "done": "Je suis revenu à la page précédente",
            },
            "browser_forward": {
                "will": "Je vais avancer à la page suivante",
                "cannot": "Je n'ai pas pu avancer",
                "done": "Je suis passé à la page suivante",
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
            "browser_pilotage_paused": "Pilotage du navigateur arrêté par l'utilisateur",
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
            "browser_type": {
                "will": "I will type into element {ref}",
                "cannot": "I could not type the text",
                "done": "I typed into element {ref}",
            },
            "browser_scroll": {
                "will": "I will scroll the page {direction}",
                "cannot": "I could not scroll the page",
                "done": "I scrolled the page {direction}",
            },
            "browser_press": {
                "will": "I will press key {press_key}",
                "cannot": "I could not press the key",
                "done": "I pressed key {press_key}",
            },
            "browser_back": {
                "will": "I will go back to the previous page",
                "cannot": "I could not go back",
                "done": "I went back to the previous page",
            },
            "browser_forward": {
                "will": "I will go forward to the next page",
                "cannot": "I could not go forward",
                "done": "I went forward to the next page",
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
            "browser_pilotage_paused": "Browser piloting was stopped by the user",
            "browser_ref_missing": "Element reference is required",
            "browser_selector_missing": "CSS selector is required",
        },
    },
}
