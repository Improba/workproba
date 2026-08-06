"""Prompt de délégation vers les agents métier du catalogue managé."""

from __future__ import annotations

from app.i18n import t
from app.plugins.workproba_personas.storage import JsonDict

_BLURB_MAX_LEN = 160


def _specialist_blurb(specialist: JsonDict) -> str:
    text = ""
    doctrine = specialist.get("doctrine")
    if isinstance(doctrine, dict):
        mission = doctrine.get("mission")
        if isinstance(mission, str) and mission.strip():
            text = mission.strip()
    if not text:
        for key in ("description", "role"):
            value = specialist.get(key)
            if isinstance(value, str) and value.strip():
                text = value.strip()
                break
    text = " ".join(text.split())
    if len(text) > _BLURB_MAX_LEN:
        text = f"{text[: _BLURB_MAX_LEN - 3].rstrip()}..."
    return text


def _specialist_connectors(specialist: JsonDict) -> list[str]:
    tools = specialist.get("tools")
    if not isinstance(tools, dict):
        return []
    allowed = tools.get("allowed")
    if not isinstance(allowed, list):
        return []
    connectors: set[str] = set()
    for entry in allowed:
        if not isinstance(entry, dict):
            continue
        connector_id = entry.get("connector_id")
        if isinstance(connector_id, str) and connector_id.strip():
            connectors.add(connector_id.strip())
    return sorted(connectors)


def _format_specialist_line(locale: str, specialist: JsonDict) -> str:
    specialist_id = str(specialist.get("id") or "")
    name = str(specialist.get("name") or specialist_id)
    blurb = _specialist_blurb(specialist)
    connectors = _specialist_connectors(specialist)
    line = f"- {specialist_id} - {name}"
    if blurb:
        line = f"{line} - {blurb}"
    if connectors:
        suffix = t(
            locale,
            "prompt.delegation.connectors_suffix",
            connectors=", ".join(connectors),
        )
        line = f"{line} {suffix}"
    return line


def build_business_agents_delegation_prompt(
    locale: str,
    specialists: list[JsonDict],
) -> str:
    """Construit le fragment system prompt listant les agents métier déléguables."""
    if not specialists:
        return t(locale, "prompt.delegation.empty")
    lines = [
        t(locale, "prompt.delegation.header"),
        t(locale, "prompt.delegation.rule_connector_actions"),
        t(locale, "prompt.delegation.rule_modes"),
        t(locale, "prompt.delegation.rule_no_managed"),
        t(locale, "prompt.delegation.rule_no_simulate"),
        t(locale, "prompt.delegation.rule_ask_personas"),
    ]
    for specialist in specialists:
        lines.append(_format_specialist_line(locale, specialist))
    return "\n".join(lines)
