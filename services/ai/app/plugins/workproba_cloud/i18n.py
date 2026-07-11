"""Traductions du plugin cloud."""

from __future__ import annotations

from typing import Any

MESSAGES: dict[str, dict[str, Any]] = {
    "fr": {
        "human": {
            "sync_to_cloud": {
                "will": "Je vais synchroniser le projet {project_id} vers le cloud local",
                "cannot": "Je n'ai pas pu synchroniser le projet {project_id}",
                "done": "J'ai synchronisé {count} document(s) du projet {project_id}",
            },
        },
        "plugin": {
            "workproba": {
                "cloud": {
                    "name": "Cloud",
                    "coming_soon": "Bientôt disponible",
                },
            },
        },
    },
    "en": {
        "human": {
            "sync_to_cloud": {
                "will": "I will sync project {project_id} to the local cloud folder",
                "cannot": "I could not sync project {project_id}",
                "done": "I synced {count} document(s) from project {project_id}",
            },
        },
        "plugin": {
            "workproba": {
                "cloud": {
                    "name": "Cloud",
                    "coming_soon": "Coming soon",
                },
            },
        },
    },
}
