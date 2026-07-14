"""Promotion de résumés de session vers la mémoire project (consolidation locale)."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Literal

from pydantic_ai import Agent

from app.agent.memory_ranking import _normalize_content, _tokenize
from app.audit import log_event, resolve_app_data_dir
from app.i18n import DEFAULT_LOCALE, t
from app.llm.config import build_model, build_model_settings
from app.llm.utility import resolve_utility_config
from app.rag.store import RagStore
from app.schemas import LLMProviderConfig

logger = logging.getLogger(__name__)

ConsolidationOperation = Literal["ADD", "UPDATE", "NOOP", "DELETE"]
ContradictionAction = Literal["UPDATE", "DELETE", "NOOP"]


def token_jaccard(left: str, right: str) -> float:
    left_tokens = _tokenize(left)
    right_tokens = _tokenize(right)
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    return intersection / union if union else 0.0


def find_matching_memory(
    memories: list[dict[str, Any]],
    new_fact: str,
    *,
    update_threshold: float,
) -> tuple[ConsolidationOperation, dict[str, Any] | None, float]:
    """Décide ADD / UPDATE / NOOP pour un fait candidat, avec score de recouvrement."""
    cleaned = new_fact.strip()
    if not cleaned:
        return "NOOP", None, 0.0

    normalized_new = _normalize_content(cleaned)
    best_match: dict[str, Any] | None = None
    best_score = 0.0

    for memory in memories:
        content = str(memory.get("content") or "").strip()
        if not content:
            continue
        if _normalize_content(content) == normalized_new:
            return "NOOP", memory, 1.0
        score = token_jaccard(content, cleaned)
        if score > best_score:
            best_score = score
            best_match = memory

    if best_match is not None and best_score >= update_threshold:
        return "UPDATE", best_match, best_score
    return "ADD", None, best_score


def parse_contradiction_action(text: str) -> ContradictionAction:
    """Parse la décision LLM UPDATE / DELETE / NOOP."""
    stripped = text.strip()
    if not stripped:
        return "UPDATE"

    payloads: list[dict[str, Any]] = []
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            payloads.append(parsed)
    except json.JSONDecodeError:
        object_match = re.search(r"\{[\s\S]*\}", stripped)
        if object_match:
            try:
                parsed = json.loads(object_match.group(0))
                if isinstance(parsed, dict):
                    payloads.append(parsed)
            except json.JSONDecodeError:
                pass

    for payload in payloads:
        action = str(payload.get("action") or "").strip().upper()
        if action in {"UPDATE", "DELETE", "NOOP"}:
            return action  # type: ignore[return-value]

    return "UPDATE"


async def resolve_ambiguous_update(
    new_fact: str,
    existing_fact: str,
    *,
    locale: str,
    settings: Any,
    utility_llm_config: LLMProviderConfig | None,
    chat_llm_config: LLMProviderConfig | None,
) -> ContradictionAction:
    """Demande au LLM utilitaire comment traiter un UPDATE ambigu."""
    config = resolve_utility_config(utility_llm_config, chat_llm_config, settings)
    agent = Agent(
        build_model(config),
        system_prompt=t(locale, "utility.fact_contradiction_system_prompt"),
        output_type=str,
        model_settings=build_model_settings(config),
    )
    result = await agent.run(
        t(
            locale,
            "utility.fact_contradiction_user_prompt",
            new_fact=new_fact.strip(),
            existing_fact=existing_fact.strip(),
        )
    )
    output = getattr(result, "output", result)
    text = output if isinstance(output, str) else str(output)
    return parse_contradiction_action(text)


def log_promotion_event(
    workspace_data_dir: Path,
    *,
    session_id: str,
    counts: dict[str, int],
    facts: list[str],
    pruned: int,
) -> None:
    """Journalise une promotion inter-session (audit + logger applicatif)."""
    details = {
        "session_id": session_id,
        "counts": counts,
        "facts_extracted": len(facts),
        "pruned": pruned,
    }
    try:
        log_event(
            resolve_app_data_dir(workspace_data_dir),
            "memory.promotion",
            "system",
            details,
        )
    except Exception:
        logger.exception("Échec écriture audit memory.promotion")
    logger.info(
        "memory.promotion session=%s counts=%s facts=%d pruned=%d",
        session_id,
        counts,
        len(facts),
        pruned,
    )


def trim_project_memory_store(store: RagStore, max_entries: int) -> int:
    """Applique le plafond LRU sur les souvenirs explicites project."""
    return store.trim_memories_to_cap(max_entries, actor="system")


def session_has_promoted_facts(store: RagStore, session_id: str) -> bool:
    """Indique si une session a déjà des faits promus en mémoire project."""
    tag = f"session:{session_id}"
    return any(tag in (memory.get("tags") or []) for memory in store.list_memories())


def apply_explicit_memory_heuristic(
    store: RagStore,
    content: str,
    *,
    source: str,
    tags: list[str] | None = None,
    update_threshold: float = 0.55,
) -> tuple[dict[str, Any], ConsolidationOperation]:
    """Consolidation heuristique sans LLM (remember / add manuel)."""
    cleaned = content.strip()
    if not cleaned:
        raise ValueError("empty_memory_content")

    memories = store.list_memories()
    operation, match, _score = find_matching_memory(
        memories,
        cleaned,
        update_threshold=update_threshold,
    )
    tag_list = tags or []

    if operation == "NOOP" and match is not None:
        return match, "NOOP"

    if operation == "UPDATE" and match is not None:
        memory = store.add_memory(
            content=cleaned,
            source=source,
            tags=tag_list,
            memory_id=str(match["id"]),
        )
        return memory, "UPDATE"

    memory = store.add_memory(content=cleaned, source=source, tags=tag_list)
    return memory, "ADD"


async def apply_fact_to_store(
    store: RagStore,
    fact: str,
    session_id: str,
    *,
    update_threshold: float,
    contradiction_enabled: bool,
    locale: str,
    settings: Any,
    utility_llm_config: LLMProviderConfig | None = None,
    chat_llm_config: LLMProviderConfig | None = None,
) -> dict[str, Any]:
    """Applique un fait au store project avec résolution ADD/UPDATE/NOOP/DELETE."""
    cleaned = fact.strip()
    if not cleaned:
        return {"operation": "NOOP", "memory": None}

    memories = store.list_memories()
    operation, match, score = find_matching_memory(
        memories,
        cleaned,
        update_threshold=update_threshold,
    )
    tags = [f"session:{session_id}", "promoted"]

    if operation == "NOOP":
        return {"operation": "NOOP", "memory": match, "score": score}

    if operation == "UPDATE" and match is not None:
        existing_content = str(match.get("content") or "").strip()
        action: ContradictionAction = "UPDATE"
        if contradiction_enabled and existing_content:
            try:
                action = await resolve_ambiguous_update(
                    cleaned,
                    existing_content,
                    locale=locale,
                    settings=settings,
                    utility_llm_config=utility_llm_config,
                    chat_llm_config=chat_llm_config,
                )
            except Exception:
                logger.warning(
                    "Contradiction LLM failed for session=%s, fallback UPDATE",
                    session_id,
                    exc_info=True,
                )
                action = "UPDATE"

        if action == "NOOP":
            return {"operation": "NOOP", "memory": match, "score": score}

        if action == "DELETE":
            memory_id = str(match.get("id") or "")
            if not memory_id:
                memory = store.add_memory(
                    content=cleaned,
                    source="session_promotion",
                    tags=tags,
                )
                return {"operation": "ADD", "memory": memory, "score": score}

            deleted = store.forget_memory(
                memory_id,
                actor="system",
                scope="contradiction",
            )
            if not deleted:
                return {"operation": "NOOP", "memory": match, "score": score}

            memory = store.add_memory(
                content=cleaned,
                source="session_promotion",
                tags=tags,
            )
            return {
                "operation": "DELETE",
                "memory": memory,
                "replaced_memory_id": memory_id,
                "score": score,
            }

        memory = store.add_memory(
            content=cleaned,
            source="session_promotion",
            tags=tags,
            memory_id=str(match["id"]),
        )
        return {"operation": "UPDATE", "memory": memory, "score": score}

    memory = store.add_memory(
        content=cleaned,
        source="session_promotion",
        tags=tags,
    )
    return {"operation": "ADD", "memory": memory, "score": score}


async def consolidate_facts(
    store: RagStore,
    facts: list[str],
    session_id: str,
    *,
    max_facts: int,
    update_threshold: float,
    contradiction_enabled: bool,
    locale: str,
    settings: Any,
    utility_llm_config: LLMProviderConfig | None = None,
    chat_llm_config: LLMProviderConfig | None = None,
    max_entries: int = 0,
) -> dict[str, Any]:
    """Consolide une liste de faits dans le store project."""
    results: list[dict[str, Any]] = []
    counts = {"ADD": 0, "UPDATE": 0, "NOOP": 0, "DELETE": 0}

    for fact in facts[:max_facts]:
        outcome = await apply_fact_to_store(
            store,
            fact,
            session_id,
            update_threshold=update_threshold,
            contradiction_enabled=contradiction_enabled,
            locale=locale,
            settings=settings,
            utility_llm_config=utility_llm_config,
            chat_llm_config=chat_llm_config,
        )
        operation = str(outcome.get("operation") or "NOOP")
        if operation in counts:
            counts[operation] += 1
        results.append(outcome)

    pruned = trim_project_memory_store(store, max_entries) if max_entries > 0 else 0

    return {
        "results": results,
        "counts": counts,
        "facts": facts[:max_facts],
        "pruned": pruned,
    }


def parse_facts_from_llm_output(text: str, *, max_facts: int) -> list[str]:
    """Parse la sortie LLM (JSON array ou puces) en faits atomiques."""
    stripped = text.strip()
    if not stripped:
        return []

    candidates: list[str] = []
    try:
        payload = json.loads(stripped)
        if isinstance(payload, list):
            candidates = [str(item).strip() for item in payload if str(item).strip()]
    except json.JSONDecodeError:
        array_match = re.search(r"\[[\s\S]*\]", stripped)
        if array_match:
            try:
                payload = json.loads(array_match.group(0))
                if isinstance(payload, list):
                    candidates = [
                        str(item).strip() for item in payload if str(item).strip()
                    ]
            except json.JSONDecodeError:
                candidates = []

    if not candidates:
        for line in stripped.splitlines():
            cleaned = re.sub(r"^[\-\*\d\.\)\s]+", "", line).strip()
            if cleaned:
                candidates.append(cleaned)

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = _normalize_content(candidate)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
        if len(deduped) >= max_facts:
            break
    return deduped


async def extract_facts_from_summary(
    summary: str,
    *,
    locale: str,
    settings: Any,
    utility_llm_config: LLMProviderConfig | None,
    chat_llm_config: LLMProviderConfig | None,
    max_facts: int,
) -> list[str]:
    """Extrait des faits durables depuis un résumé de session via le LLM utilitaire."""
    cleaned_summary = summary.strip()
    if not cleaned_summary:
        return []

    config = resolve_utility_config(utility_llm_config, chat_llm_config, settings)
    agent = Agent(
        build_model(config),
        system_prompt=t(locale, "utility.fact_extraction_system_prompt"),
        output_type=str,
        model_settings=build_model_settings(config),
    )
    result = await agent.run(
        t(
            locale,
            "utility.fact_extraction_user_prompt",
            summary=cleaned_summary,
            max_facts=max_facts,
        )
    )
    output = getattr(result, "output", result)
    text = output if isinstance(output, str) else str(output)
    return parse_facts_from_llm_output(text, max_facts=max_facts)


async def promote_session_summary(
    store: RagStore,
    *,
    summary: str,
    session_id: str,
    workspace_data_dir: Path,
    locale: str = DEFAULT_LOCALE,
    settings: Any,
    utility_llm_config: LLMProviderConfig | None = None,
    chat_llm_config: LLMProviderConfig | None = None,
    max_facts: int = 5,
    update_threshold: float = 0.55,
    contradiction_enabled: bool = True,
    max_entries: int = 200,
) -> dict[str, Any]:
    """Pipeline complet : extraction LLM, consolidation locale, plafond et audit."""
    facts = await extract_facts_from_summary(
        summary,
        locale=locale,
        settings=settings,
        utility_llm_config=utility_llm_config,
        chat_llm_config=chat_llm_config,
        max_facts=max_facts,
    )
    consolidation = await consolidate_facts(
        store,
        facts,
        session_id,
        max_facts=max_facts,
        update_threshold=update_threshold,
        contradiction_enabled=contradiction_enabled,
        locale=locale,
        settings=settings,
        utility_llm_config=utility_llm_config,
        chat_llm_config=chat_llm_config,
        max_entries=max_entries,
    )
    counts = dict(consolidation.get("counts") or {})
    pruned = int(consolidation.get("pruned") or 0)
    if facts:
        log_promotion_event(
            workspace_data_dir,
            session_id=session_id,
            counts=counts,
            facts=facts,
            pruned=pruned,
        )
    return {
        "session_id": session_id,
        **consolidation,
    }
