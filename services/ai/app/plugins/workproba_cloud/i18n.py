"""Traductions du plugin cloud."""

from __future__ import annotations

from typing import Any

MESSAGES: dict[str, dict[str, Any]] = {
    "fr": {
        "human": {
            "sync_to_cloud": {
                "will": "Je vais synchroniser le cache avancé des documents publiés de {project_id} (dossier et/ou cloud)",
                "cannot": "Je n'ai pas pu synchroniser le cache avancé des documents de {project_id}",
                "done": "J'ai synchronisé {count} document(s) publié(s) de {project_id} (cache avancé)",
            },
            "sync_from_cloud": {
                "will": "Je vais récupérer les documents du projet {project_id} depuis le cloud",
                "cannot": "Je n'ai pas pu récupérer les documents du projet {project_id} depuis le cloud",
                "done": "J'ai récupéré {count} document(s) du projet {project_id} depuis le cloud",
            },
            "enroll_to_cloud": {
                "will": "Je vais me connecter à Improba Cloud",
                "cannot": "Je n'ai pas pu me connecter à Improba Cloud",
                "done": "Je suis connecté à Improba Cloud",
            },
            "sync_managed_regards": {
                "will": "Je vais synchroniser les regards de l'organisation",
                "cannot": "Je n'ai pas pu synchroniser les regards de l'organisation",
                "done": "J'ai synchronisé {count} regard(s) de l'organisation",
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
                "will": "I will sync the advanced cache of published documents from {project_id} (folder and/or cloud)",
                "cannot": "I could not sync the advanced cache for documents from {project_id}",
                "done": "I synced {count} published document(s) from {project_id} (advanced cache)",
            },
            "sync_from_cloud": {
                "will": "I will pull documents for project {project_id} from the cloud",
                "cannot": "I could not pull documents for project {project_id} from the cloud",
                "done": "I pulled {count} document(s) for project {project_id} from the cloud",
            },
            "enroll_to_cloud": {
                "will": "I will sign in to Improba Cloud",
                "cannot": "I could not sign in to Improba Cloud",
                "done": "I am signed in to Improba Cloud",
            },
            "sync_managed_regards": {
                "will": "I will sync organization regards",
                "cannot": "I could not sync organization regards",
                "done": "I synced {count} organization regard(s)",
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
