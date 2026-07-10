"""Résumés lisibles des appels d'outils pour l'UI non-codeur."""

from __future__ import annotations

from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]


def _basename(value: str) -> str:
    cleaned = value.strip().strip("/")
    if not cleaned:
        return "le projet"
    return Path(cleaned).name or cleaned


def _format_location(subdir: str) -> str:
    cleaned = subdir.strip().strip("/")
    if not cleaned or cleaned == ".":
        return "du projet"
    return f"du dossier {_basename(cleaned)}"


def _format_query(query: str) -> str:
    text = query.strip()
    if not text:
        return "cette recherche"
    if len(text) > 80:
        text = f"{text[:77]}..."
    return f"« {text} »"


def _read_detail(result: JsonDict) -> str:
    metadata = result.get("metadata")
    if isinstance(metadata, dict):
        pages_total = metadata.get("pages_total")
        if isinstance(pages_total, int) and pages_total > 0:
            return f" ({pages_total} pages)"
        lines_returned = metadata.get("lines_returned")
        if isinstance(lines_returned, int) and lines_returned > 0:
            return f" ({lines_returned} lignes)"
    return ""


def build_human_summary(
    tool_name: str,
    args: JsonDict | None = None,
    *,
    result: JsonDict | None = None,
    is_error: bool = False,
) -> str:
    """Construit une phrase française pour tool_call_start ou tool_call_result."""
    arguments = args or {}
    is_result = result is not None

    if tool_name == "list_files":
        location = _format_location(str(arguments.get("subdir") or ""))
        if is_result:
            if is_error:
                return f"Je n'ai pas pu lister les fichiers {location}"
            raw_entries = result.get("entries")
            entries = raw_entries if isinstance(raw_entries, list) else []
            count = len(entries)
            if count == 0:
                return f"J'ai listé les fichiers {location} (aucun élément)"
            label = "élément" if count == 1 else "éléments"
            return f"J'ai listé les fichiers {location} ({count} {label})"
        return f"Je vais lister les fichiers {location}"

    if tool_name == "search_kb":
        query_label = _format_query(str(arguments.get("query") or ""))
        if is_result:
            if is_error:
                return f"Je n'ai pas pu chercher {query_label} dans les fichiers"
            raw_results = result.get("results")
            results = raw_results if isinstance(raw_results, list) else []
            count = len(results)
            if count == 0:
                return f"Je n'ai trouvé aucun résultat pour {query_label}"
            label = "résultat" if count == 1 else "résultats"
            return f"J'ai trouvé {count} {label} pour {query_label}"
        return f"Je vais chercher {query_label} dans les fichiers"

    if tool_name == "read_document":
        doc_id = str(arguments.get("document_id") or "ce document")
        name = _basename(doc_id)
        if is_result:
            if is_error:
                return f"Je n'ai pas pu lire {name}"
            return f"J'ai lu {name}{_read_detail(result)}"
        return f"Je vais lire {name}"

    if tool_name == "run_code":
        if is_result:
            if is_error:
                return "Je n'ai pas pu exécuter le calcul"
            return "J'ai exécuté un calcul"
        return "Je vais exécuter un calcul"

    if tool_name == "generate_document":
        name = _basename(str(arguments.get("name") or "ce document"))
        if is_result:
            if is_error:
                return f"Je n'ai pas pu créer {name}"
            return f"J'ai créé {name}"
        return f"Je vais créer {name}"

    if is_result:
        if is_error:
            return "Je n'ai pas pu terminer cette action"
        return "J'ai terminé cette action"
    return "Je vais effectuer une action"
