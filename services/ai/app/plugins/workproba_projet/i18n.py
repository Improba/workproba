"""Traductions du plugin projet (namespace plugin.workproba.projet.*)."""

from __future__ import annotations

from typing import Any

MESSAGES: dict[str, dict[str, Any]] = {
    "fr": {
        "human": {
            "publish_artifact": {
                "will": "Je vais publier {name} dans le projet {project}",
                "cannot": "Je n'ai pas pu publier {name} dans le projet {project}",
                "done": "J'ai publié {name} dans le projet {project}",
            },
            "create_project": {
                "will": "Je vais créer le projet {name}",
                "cannot": "Je n'ai pas pu créer le projet {name}",
                "done": "J'ai créé le projet {name}",
            },
            "list_projects": {
                "will": "Je vais lister les projets",
                "cannot": "Je n'ai pas pu lister les projets",
                "empty": "Aucun projet pour le moment",
                "count": {
                    "one": "J'ai listé {count} projet",
                    "many": "J'ai listé {count} projets",
                },
            },
        },
        "plugin": {
            "workproba": {
                "projet": {
                    "name": "Projet",
                    "tab_title": "Projet",
                    "publish_action": "Publier dans le projet",
                    "artefact_label": "Document publié",
                },
            },
        },
        "errors": {
            "project_not_found": "Projet introuvable : {project_id}",
            "source_not_found": "Fichier source introuvable : {path}",
            "path_outside_workspace": "Chemin hors de l'espace de travail",
            "invalid_project_name": "Nom de projet invalide",
            "invalid_artefact_name": "Nom de document invalide",
            "missing_publish_source": "Indiquez un fichier source ou un contenu markdown",
            "ambiguous_publish_source": "Indiquez soit un fichier source, soit un contenu markdown",
            "content_too_large": "Le contenu dépasse la taille maximale autorisée",
            "missing_workspace_root": "Espace de travail requis pour publier un fichier",
        },
    },
    "en": {
        "human": {
            "publish_artifact": {
                "will": "I will publish {name} in project {project}",
                "cannot": "I could not publish {name} in project {project}",
                "done": "I published {name} in project {project}",
            },
            "create_project": {
                "will": "I will create project {name}",
                "cannot": "I could not create project {name}",
                "done": "I created project {name}",
            },
            "list_projects": {
                "will": "I will list projects",
                "cannot": "I could not list projects",
                "empty": "No projects yet",
                "count": {
                    "one": "I listed {count} project",
                    "many": "I listed {count} projects",
                },
            },
        },
        "plugin": {
            "workproba": {
                "projet": {
                    "name": "Project",
                    "tab_title": "Project",
                    "publish_action": "Publish to project",
                    "artefact_label": "Published document",
                },
            },
        },
        "errors": {
            "project_not_found": "Project not found: {project_id}",
            "source_not_found": "Source file not found: {path}",
            "path_outside_workspace": "Path outside workspace",
            "invalid_project_name": "Invalid project name",
            "invalid_artefact_name": "Invalid document name",
            "missing_publish_source": "Provide a source file or markdown content",
            "ambiguous_publish_source": "Provide either a source file or markdown content",
            "content_too_large": "Content exceeds the maximum allowed size",
            "missing_workspace_root": "Workspace required to publish a file",
        },
    },
}
