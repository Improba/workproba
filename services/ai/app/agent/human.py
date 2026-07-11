"""Résumés lisibles des appels d'outils pour l'UI non-codeur."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.i18n import DEFAULT_LOCALE, format_summary, t

JsonDict = dict[str, Any]


def _basename(value: str, locale: str) -> str:
    cleaned = value.strip().strip("/")
    if not cleaned:
        return t(locale, "human.space_default")
    return Path(cleaned).name or cleaned


def _format_location(subdir: str, locale: str) -> str:
    cleaned = subdir.strip().strip("/")
    if not cleaned or cleaned == ".":
        return t(locale, "human.location_root")
    return t(locale, "human.location_subdir", name=_basename(cleaned, locale))


def _format_query(query: str, locale: str) -> str:
    text = query.strip()
    if not text:
        return t(locale, "human.query_default")
    if len(text) > 80:
        text = f"{text[:77]}..."
    return t(locale, "human.query_labeled", text=text)


def _read_detail(result: JsonDict, locale: str) -> str:
    metadata = result.get("metadata")
    if isinstance(metadata, dict):
        pages_total = metadata.get("pages_total")
        if isinstance(pages_total, int) and pages_total > 0:
            return t(locale, "human.detail_pages", pages=pages_total)
        lines_returned = metadata.get("lines_returned")
        if isinstance(lines_returned, int) and lines_returned > 0:
            return t(locale, "human.detail_lines", lines=lines_returned)
    return ""


def build_human_summary(
    tool_name: str,
    args: JsonDict | None = None,
    *,
    result: JsonDict | None = None,
    is_error: bool = False,
    locale: str = DEFAULT_LOCALE,
) -> str:
    """Construit une phrase localisée pour tool_call_start ou tool_call_result."""
    arguments = args or {}
    is_result = result is not None

    if tool_name == "list_files":
        location = _format_location(str(arguments.get("subdir") or ""), locale)
        if is_result:
            if is_error:
                return t(locale, "human.list_files.cannot", location=location)
            raw_entries = result.get("entries")
            entries = raw_entries if isinstance(raw_entries, list) else []
            count = len(entries)
            if count == 0:
                return t(locale, "human.list_files.empty", location=location)
            return format_summary(
                locale,
                "human.list_files.count",
                {"location": location},
                count,
            )
        return t(locale, "human.list_files.will", location=location)

    if tool_name == "search_kb":
        query_label = _format_query(str(arguments.get("query") or ""), locale)
        if is_result:
            if is_error:
                return t(locale, "human.search_kb.cannot", query=query_label)
            raw_results = result.get("results")
            results = raw_results if isinstance(raw_results, list) else []
            count = len(results)
            if count == 0:
                return t(locale, "human.search_kb.empty", query=query_label)
            return format_summary(
                locale,
                "human.search_kb.count",
                {"query": query_label},
                count,
            )
        return t(locale, "human.search_kb.will", query=query_label)

    if tool_name == "read_document":
        doc_id = str(
            arguments.get("document_id") or t(locale, "human.document_default")
        )
        name = _basename(doc_id, locale)
        if is_result:
            if is_error:
                return t(locale, "human.read_document.cannot", name=name)
            return t(
                locale,
                "human.read_document.done",
                name=name,
                detail=_read_detail(result, locale),
            )
        return t(locale, "human.read_document.will", name=name)

    if tool_name == "run_code":
        if is_result:
            if is_error:
                return t(locale, "human.run_code.cannot")
            return t(locale, "human.run_code.done")
        return t(locale, "human.run_code.will")

    if tool_name == "generate_document":
        name = _basename(
            str(arguments.get("name") or t(locale, "human.document_default")),
            locale,
        )
        if is_result:
            if is_error:
                return t(locale, "human.generate_document.cannot", name=name)
            return t(locale, "human.generate_document.done", name=name)
        return t(locale, "human.generate_document.will", name=name)

    for office_tool, key_prefix in (
        ("write_docx", "human.write_docx"),
        ("write_xlsx", "human.write_xlsx"),
        ("write_pdf", "human.write_pdf"),
    ):
        if tool_name == office_tool:
            filename = _basename(
                str(
                    arguments.get("path")
                    or arguments.get("name")
                    or t(locale, "human.document_default")
                ),
                locale,
            )
            if is_result:
                if is_error:
                    return t(locale, f"{key_prefix}.cannot", filename=filename)
                return t(locale, f"{key_prefix}.done", filename=filename)
            return t(locale, f"{key_prefix}.will", filename=filename)

    if tool_name == "publish_artifact":
        artefact_name = _basename(
            str(arguments.get("name") or t(locale, "human.document_default")),
            locale,
        )
        project_name = str(
            arguments.get("project")
            or arguments.get("project_name")
            or arguments.get("project_id")
            or ""
        )
        if is_result:
            if is_error or result.get("cancelled"):
                return t(
                    locale,
                    "human.publish_artifact.cannot",
                    name=artefact_name,
                    project=project_name,
                )
            resolved_project = str(
                result.get("project_name") or result.get("project_id") or project_name
            )
            return t(
                locale,
                "human.publish_artifact.done",
                name=artefact_name,
                project=resolved_project,
            )
        return t(
            locale,
            "human.publish_artifact.will",
            name=artefact_name,
            project=project_name,
        )

    if tool_name == "create_project":
        project_name = str(arguments.get("name") or "").strip()
        if is_result:
            if is_error:
                return t(locale, "human.create_project.cannot", name=project_name)
            created_name = str((result.get("project") or {}).get("name") or project_name)
            return t(locale, "human.create_project.done", name=created_name)
        return t(locale, "human.create_project.will", name=project_name)

    if tool_name == "sync_to_cloud":
        project_id = str(arguments.get("project_id") or "")
        if is_result:
            if is_error:
                return t(locale, "human.sync_to_cloud.cannot", project_id=project_id)
            count = int(result.get("count") or len(result.get("synced") or []))
            return t(
                locale,
                "human.sync_to_cloud.done",
                project_id=project_id,
                count=count,
            )
        return t(locale, "human.sync_to_cloud.will", project_id=project_id)

    if tool_name == "list_projects":
        if is_result:
            if is_error:
                return t(locale, "human.list_projects.cannot")
            count = int(result.get("count") or 0)
            if count == 0:
                return t(locale, "human.list_projects.empty")
            return format_summary(locale, "human.list_projects.count", count=count)
        return t(locale, "human.list_projects.will")

    if tool_name == "ask_personas":
        names = str(arguments.get("names") or arguments.get("persona_ids") or "")
        if is_result:
            if is_error:
                return t(locale, "human.ask_personas.cannot")
            return format_summary(
                locale,
                "human.ask_personas.done",
                {"names": names},
                count=len(result.get("opinions") or []),
            )
        return t(locale, "human.ask_personas.will", names=names)

    if tool_name == "simulate_meeting":
        names = str(arguments.get("names") or "")
        topic = str(arguments.get("topic") or "")
        rounds = int(arguments.get("rounds") or 3)
        if is_result:
            if is_error:
                return t(locale, "human.simulate_meeting.cannot")
            return t(
                locale,
                "human.simulate_meeting.done",
                names=names,
                rounds=rounds,
            )
        return t(
            locale,
            "human.simulate_meeting.will",
            names=names,
            topic=topic,
            rounds=rounds,
        )

    for browser_tool, key_prefix in (
        ("browser_navigate", "human.browser_navigate"),
        ("browser_click", "human.browser_click"),
        ("browser_extract", "human.browser_extract"),
    ):
        if tool_name == browser_tool:
            label_key = "url" if browser_tool == "browser_navigate" else (
                "ref" if browser_tool == "browser_click" else "selector"
            )
            label_value = str(arguments.get(label_key) or "")
            if is_result:
                if is_error:
                    return t(locale, f"{key_prefix}.cannot")
                return t(locale, f"{key_prefix}.done", **{label_key: label_value})
            return t(locale, f"{key_prefix}.will", **{label_key: label_value})

    if is_result:
        if is_error:
            return t(locale, "human.generic.cannot_finish")
        return t(locale, "human.generic.finished")
    return t(locale, "human.generic.will_act")
