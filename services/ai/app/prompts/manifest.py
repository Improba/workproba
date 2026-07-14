"""Collecte du manifest prompt (refs + empreintes) pour l'audit ``turn.prompt``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic_ai import Agent

from app.agent.tools import ToolDeps
from app.config import get_settings
from app.llm.config import build_model_settings, resolve_llm_config
from app.plugins.registry import PLUGIN_WORKPROBA_PERSONAS, is_plugin_active
from app.prompts.registry import (
    DYNAMIC_HOOK_SPECS,
    PROMPT_SPECS,
    combined_sha256,
    prompt_ref,
    redact_model_settings,
    sha256_text,
    template_sha256,
)
from app.schemas import AgentTurnRequest


@dataclass
class _ManifestRunContext:
    """Contexte minimal pour exécuter les hooks ``@agent.system_prompt``."""

    deps: ToolDeps


def collect_prompt_manifest(
    agent: Agent[ToolDeps, str],
    deps: ToolDeps,
) -> dict[str, Any]:
    """Construit refs, empreintes et variables sûres du prompt système.

    Les hooks dynamiques sont exécutés une fois ici pour l'audit uniquement ;
    pydantic-ai les ré-exécute pendant ``agent.iter`` (double appel acceptable
    en MVP tant que le contexte est identique).
    """
    locale = deps.context.locale
    prompt_refs: list[dict[str, Any]] = []
    digest_pairs: list[tuple[str, str]] = []

    for i18n_key, placeholders in PROMPT_SPECS.items():
        ref = prompt_ref(i18n_key)
        digest = template_sha256(locale, i18n_key, **placeholders)
        prompt_refs.append({"ref": ref, "kind": "static", "sha256": digest})
        digest_pairs.append((ref, digest))

    manifest_ctx = _ManifestRunContext(deps=deps)
    for runner in agent._system_prompt_functions:
        hook_name = runner.function.__name__
        ref = DYNAMIC_HOOK_SPECS.get(hook_name)
        if ref is None:
            continue
        try:
            output = runner.function(manifest_ctx)
        except Exception:
            output = ""
        text = output if isinstance(output, str) else str(output or "")
        digest = sha256_text(text)
        prompt_refs.append(
            {
                "ref": ref,
                "kind": "dynamic",
                "chars": len(text),
                "sha256": digest,
                "empty": not text.strip(),
            }
        )
        digest_pairs.append((ref, digest))

    variables = _safe_variables(deps)
    return {
        "prompt_refs": prompt_refs,
        "combined_sha256": combined_sha256(digest_pairs),
        "variables": variables,
    }


def build_turn_prompt_details(
    agent: Agent[ToolDeps, str],
    deps: ToolDeps,
    request: AgentTurnRequest,
    *,
    turn_id: str,
    model_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Détails complets de l'événement audit ``turn.prompt``."""
    settings = get_settings()
    llm_config = resolve_llm_config(
        request.llm_provider_config,
        settings,
        provider_set=request.provider_set,
    )
    effective_settings = model_settings if model_settings is not None else build_model_settings(llm_config)
    manifest = collect_prompt_manifest(agent, deps)
    provider_set = request.provider_set
    provider_set_id = provider_set.id if provider_set and provider_set.id else None

    return {
        "turn_id": turn_id,
        "session_id": request.session_id,
        "locale": request.locale,
        "provider": llm_config.provider,
        "model": llm_config.model,
        "provider_set_id": provider_set_id,
        "model_settings": redact_model_settings(dict(effective_settings)),
        "active_plugins": request.active_plugins,
        **manifest,
    }


def _safe_variables(deps: ToolDeps) -> dict[str, Any]:
    context = deps.context
    active_plugins = context.active_plugins or []
    personas_active = is_plugin_active(PLUGIN_WORKPROBA_PERSONAS, active_plugins)
    personas_count = 0
    if personas_active and context.plugin_data_dir is not None:
        try:
            from app.plugins.workproba_personas import storage as personas_storage

            personas_count = len(personas_storage._persona_index(context.plugin_data_dir))
        except Exception:
            personas_count = 0

    return {
        "document_count": len(context.documents),
        "memory_count": _memory_count(context.workspace_data_dir),
        "workspace_title": context.workspace_title,
        "personas_active": personas_active,
        "personas_count": personas_count,
    }


def _memory_count(workspace_data_dir: Any) -> int | None:
    if workspace_data_dir is None:
        return None
    try:
        from app.memory_stores import open_memory_store_for_scope

        total = 0
        for scope in ("user", "project"):
            store = open_memory_store_for_scope(scope, workspace_data_dir)
            try:
                total += len(store.list_memories())
            finally:
                store.close()
        return total
    except Exception:
        return None
