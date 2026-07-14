"""Registre de versions des prompts et manifest d'audit (refs + empreintes)."""

from app.prompts.manifest import build_turn_prompt_details, collect_prompt_manifest
from app.prompts.registry import (
    DYNAMIC_HOOK_SPECS,
    PROMPT_SPECS,
    prompt_ref,
    template_sha256,
)

__all__ = [
    "DYNAMIC_HOOK_SPECS",
    "PROMPT_SPECS",
    "build_turn_prompt_details",
    "collect_prompt_manifest",
    "prompt_ref",
    "template_sha256",
]
