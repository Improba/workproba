"""Registre v1 des prompts statiques (i18n) et hooks dynamiques."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from app.i18n import t

PROMPT_VERSION = 1


def prompt_ref(key: str, version: int = PROMPT_VERSION) -> str:
    """Retourne une référence versionnée (ex. ``tools.system_prompt@1``)."""
    if "@" in key:
        return key
    return f"{key}@{version}"


# Clés i18n -> placeholders pour hasher le gabarit (vars vides ou neutres).
PROMPT_SPECS: dict[str, dict[str, Any]] = {
    "tools.system_prompt": {},
    "tools.plan_mode_prompt": {},
    "tools.sessions_note": {"count": 0},
    "tools.space_name_context": {"name": ""},
    "memory.agent_guardrail": {},
    "utility.title_system_prompt": {},
    "utility.summary_system_prompt": {},
}

DYNAMIC_HOOK_SPECS: dict[str, str] = {
    "project_inventory_prompt": prompt_ref("dynamic:inventory"),
    "project_sessions_prompt": prompt_ref("dynamic:sessions"),
    "space_name_prompt": prompt_ref("dynamic:space_name"),
    "plan_mode_instruction": prompt_ref("dynamic:plan_mode"),
    "memory_prompt": prompt_ref("dynamic:memory"),
}


def template_sha256(locale: str, i18n_key: str, **placeholders: Any) -> str:
    """Empreinte SHA-256 du texte i18n résolu (sans journaliser le contenu)."""
    text = t(locale, i18n_key, **placeholders)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def combined_sha256(pairs: list[tuple[str, str]]) -> str:
    """Empreinte combinée, ordonnée par ref (content-addressed)."""
    ordered = sorted(pairs, key=lambda item: item[0])
    payload = "\n".join(f"{ref}\0{digest}" for ref, digest in ordered)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


_SENSITIVE_KEY_RE = re.compile(r"(api[_-]?key|token|secret|authorization|password)", re.I)


def redact_model_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    """Retire les secrets des paramètres modèle avant audit."""

    def _walk(value: Any, key: str = "") -> Any:
        if _SENSITIVE_KEY_RE.search(key):
            return "[REDACTED]"
        if isinstance(value, dict):
            return {child_key: _walk(child_value, child_key) for child_key, child_value in value.items()}
        if isinstance(value, list):
            return [_walk(item) for item in value]
        return value

    if not settings:
        return {}
    return _walk(settings)
