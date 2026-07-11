"""Orchestration LLM des modes personas (avis, réunion, discussion)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from pydantic_ai import Agent

from app.i18n import t
from app.llm.config import build_model, build_model_settings, resolve_llm_config
from app.plugins.workproba_personas import manifest, storage
from app.plugins.workproba_personas.storage import JsonDict, now_iso
from app.rag.store import RagStore
from app.schemas import ProviderSet

logger = logging.getLogger(__name__)


def clamp_persona_ids(
    persona_ids: list[str],
    *,
    locale: str,
) -> tuple[list[str], list[str]]:
    """Retourne (ids_clampés, avertissements)."""
    warnings: list[str] = []
    unique: list[str] = []
    for persona_id in persona_ids:
        if persona_id not in unique:
            unique.append(persona_id)
    if len(unique) > manifest.MAX_PERSONAS:
        warnings.append(
            t(locale, "personas.personas_capped", max=manifest.MAX_PERSONAS)
        )
        unique = unique[: manifest.MAX_PERSONAS]
    return unique, warnings


def clamp_rounds(rounds: int, *, locale: str) -> tuple[int, list[str]]:
    warnings: list[str] = []
    value = rounds if rounds > 0 else manifest.DEFAULT_ROUNDS
    if value > manifest.MAX_ROUNDS:
        warnings.append(t(locale, "personas.rounds_capped", max=manifest.MAX_ROUNDS))
        value = manifest.MAX_ROUNDS
    return value, warnings


def _persona_names(personas: list[JsonDict]) -> str:
    return ", ".join(str(persona.get("name") or persona.get("id") or "") for persona in personas)


async def _memory_context(
    rag_store: RagStore | None,
    query: str,
    *,
    locale: str,
) -> str:
    if rag_store is None or not query.strip():
        return ""
    try:
        hits = await rag_store.search_combined(query=query, limit=4)
    except Exception as exc:  # noqa: BLE001
        logger.warning("personas memory search failed: %s", exc)
        return ""
    if not hits:
        return ""
    lines = [t(locale, "personas.memory_context_header")]
    for hit in hits:
        title = hit.get("title") or hit.get("document_id") or ""
        content = str(hit.get("content") or "").strip()
        if content:
            lines.append(f"- [{title}] {content[:400]}")
    return "\n".join(lines)


def _build_agent(settings: Any, provider_set: ProviderSet | None, locale: str) -> Agent[None, str]:
    llm_config = resolve_llm_config(None, settings, provider_set=provider_set)
    return Agent(
        build_model(llm_config),
        system_prompt="",
        output_type=str,
        model_settings=build_model_settings(llm_config),
    )


async def _run_persona_prompt(
    *,
    settings: Any,
    provider_set: ProviderSet | None,
    system_prompt: str,
    user_prompt: str,
    locale: str,
) -> str:
    agent = _build_agent(settings, provider_set, locale)
    result = await agent.run(user_prompt, message_history=[], deps=None)
    output = getattr(result, "output", result)
    return output.strip() if isinstance(output, str) else str(output).strip()


async def generate_opinions(
    *,
    plugin_data_dir: Any,
    persona_ids: list[str],
    question: str,
    context: str,
    settings: Any,
    provider_set: ProviderSet | None,
    locale: str,
    rag_store: RagStore | None = None,
) -> tuple[list[JsonDict], list[str]]:
    clamped_ids, warnings = clamp_persona_ids(persona_ids, locale=locale)
    personas = storage.resolve_personas(plugin_data_dir, clamped_ids)
    if not personas:
        raise ValueError("personas_not_found")

    memory_text = await _memory_context(rag_store, f"{question}\n{context}", locale=locale)
    opinions: list[JsonDict] = []
    for persona in personas:
        name = str(persona.get("name") or persona.get("id") or "")
        system_prompt = str(persona.get("system_prompt") or "")
        user_parts = [f"Question : {question.strip()}"]
        if context.strip():
            user_parts.append(f"Contexte :\n{context.strip()}")
        if memory_text:
            user_parts.append(memory_text)
        user_parts.append(
            "Donne un avis structuré et concis (5 à 12 phrases). "
            "Ne joue pas le rôle d'un assistant générique : reste dans ton persona."
        )
        content = await _run_persona_prompt(
            settings=settings,
            provider_set=provider_set,
            system_prompt=system_prompt,
            user_prompt=f"{system_prompt}\n\n" + "\n\n".join(user_parts),
            locale=locale,
        )
        opinions.append(
            {
                "persona_id": persona.get("id"),
                "persona_name": name,
                "role": persona.get("role"),
                "avatar_color": persona.get("avatar_color"),
                "content": content,
                "memory_citations": bool(memory_text),
            }
        )
    return opinions, warnings


async def stream_ask(
    *,
    plugin_data_dir: Any,
    persona_ids: list[str],
    question: str,
    context: str,
    settings: Any,
    provider_set: ProviderSet | None,
    locale: str,
    rag_store: RagStore | None = None,
) -> AsyncIterator[JsonDict]:
    clamped_ids, warnings = clamp_persona_ids(persona_ids, locale=locale)
    if warnings:
        yield {"type": "warning", "warnings": warnings}

    personas = storage.resolve_personas(plugin_data_dir, clamped_ids)
    if not personas:
        yield {"type": "error", "code": "personas_not_found"}
        return

    memory_text = await _memory_context(rag_store, f"{question}\n{context}", locale=locale)
    for persona in personas:
        name = str(persona.get("name") or persona.get("id") or "")
        system_prompt = str(persona.get("system_prompt") or "")
        user_parts = [f"Question : {question.strip()}"]
        if context.strip():
            user_parts.append(f"Contexte :\n{context.strip()}")
        if memory_text:
            user_parts.append(memory_text)
        user_parts.append(
            "Donne un avis structuré et concis (5 à 12 phrases). "
            "Reste dans ton persona."
        )
        content = await _run_persona_prompt(
            settings=settings,
            provider_set=provider_set,
            system_prompt=system_prompt,
            user_prompt=f"{system_prompt}\n\n" + "\n\n".join(user_parts),
            locale=locale,
        )
        yield {
            "type": "persona_opinion",
            "persona_id": persona.get("id"),
            "persona_name": name,
            "role": persona.get("role"),
            "avatar_color": persona.get("avatar_color"),
            "content": content,
            "memory_citations": bool(memory_text),
        }
    yield {"type": "done"}


def _format_meeting_history(turns: list[JsonDict]) -> str:
    lines: list[str] = []
    for turn in turns:
        name = turn.get("persona_name") or turn.get("persona_id") or "?"
        round_no = turn.get("round")
        content = str(turn.get("content") or "").strip()
        if content:
            lines.append(f"[Tour {round_no}] {name} : {content}")
    return "\n".join(lines)


def _facilitator_label(round_no: int, *, locale: str) -> str:
    if round_no == 1:
        return t(locale, "personas.meeting.facilitator.round1")
    return t(locale, "personas.meeting.facilitator.round_n", n=round_no)


async def stream_meeting(
    *,
    plugin_data_dir: Any,
    persona_ids: list[str],
    topic: str,
    rounds: int,
    context: str,
    settings: Any,
    provider_set: ProviderSet | None,
    locale: str,
    rag_store: RagStore | None = None,
    meeting_id: str | None = None,
) -> AsyncIterator[JsonDict]:
    resolved_meeting_id = meeting_id or storage.new_meeting_id()
    clamped_ids, persona_warnings = clamp_persona_ids(persona_ids, locale=locale)
    clamped_rounds, round_warnings = clamp_rounds(rounds, locale=locale)
    warnings = persona_warnings + round_warnings
    if warnings:
        yield {"type": "warning", "warnings": warnings, "meeting_id": resolved_meeting_id}

    personas = storage.resolve_personas(plugin_data_dir, clamped_ids)
    if not personas:
        yield {"type": "error", "code": "personas_not_found", "meeting_id": resolved_meeting_id}
        return

    memory_text = await _memory_context(rag_store, f"{topic}\n{context}", locale=locale)
    turns: list[JsonDict] = []

    yield {
        "type": "meeting_started",
        "meeting_id": resolved_meeting_id,
        "topic": topic,
        "rounds": clamped_rounds,
        "persona_ids": clamped_ids,
    }

    for round_no in range(1, clamped_rounds + 1):
        yield {
            "type": "meeting_facilitator",
            "meeting_id": resolved_meeting_id,
            "round": round_no,
            "label": _facilitator_label(round_no, locale=locale),
        }
        for persona in personas:
            name = str(persona.get("name") or persona.get("id") or "")
            system_prompt = str(persona.get("system_prompt") or "")
            history = _format_meeting_history(turns)
            user_parts = [f"Sujet de la réunion : {topic.strip()}"]
            if context.strip():
                user_parts.append(f"Contexte :\n{context.strip()}")
            if memory_text:
                user_parts.append(memory_text)
            if history:
                user_parts.append(f"Interventions précédentes :\n{history}")
            if round_no == 1:
                user_parts.append(
                    "C'est ton premier tour de table. Donne ton point de vue initial."
                )
            else:
                user_parts.append(
                    "Réagis aux interventions précédentes et approfondis ton point de vue."
                )
            content = await _run_persona_prompt(
                settings=settings,
                provider_set=provider_set,
                system_prompt=system_prompt,
                user_prompt=f"{system_prompt}\n\n" + "\n\n".join(user_parts),
                locale=locale,
            )
            turn = {
                "round": round_no,
                "persona_id": persona.get("id"),
                "persona_name": name,
                "role": persona.get("role"),
                "avatar_color": persona.get("avatar_color"),
                "content": content,
            }
            turns.append(turn)
            yield {"type": "meeting_turn", "meeting_id": resolved_meeting_id, **turn}

    nathalie = next((p for p in personas if p.get("id") == "06"), None)
    if nathalie is None:
        nathalie = personas[-1]
    yield {
        "type": "meeting_facilitator",
        "meeting_id": resolved_meeting_id,
        "round": 0,
        "label": t(locale, "personas.meeting.facilitator.synthesis"),
    }
    summary_prompt = (
        f"{nathalie.get('system_prompt', '')}\n\n"
        f"Sujet : {topic.strip()}\n\n"
        f"Tour de table :\n{_format_meeting_history(turns)}\n\n"
        "Produis une synthèse structurée : points clés par persona, convergences, "
        "divergences et recommandations."
    )
    summary = await _run_persona_prompt(
        settings=settings,
        provider_set=provider_set,
        system_prompt=str(nathalie.get("system_prompt") or ""),
        user_prompt=summary_prompt,
        locale=locale,
    )
    transcript = {
        "id": resolved_meeting_id,
        "topic": topic,
        "rounds": clamped_rounds,
        "persona_ids": clamped_ids,
        "created_at": now_iso(),
        "turns": turns,
        "summary": {
            "persona_id": nathalie.get("id"),
            "persona_name": nathalie.get("name"),
            "title": t(locale, "personas.meeting_summary_title"),
            "content": summary,
        },
        "warnings": warnings,
    }
    storage.save_meeting_transcript(plugin_data_dir, resolved_meeting_id, transcript)
    yield {
        "type": "meeting_summary",
        "meeting_id": resolved_meeting_id,
        "persona_id": nathalie.get("id"),
        "persona_name": nathalie.get("name"),
        "content": summary,
    }
    yield {"type": "done", "meeting_id": resolved_meeting_id}


async def stream_discuss(
    *,
    plugin_data_dir: Any,
    persona_ids: list[str],
    message: str,
    history: list[JsonDict],
    discussion_id: str | None,
    settings: Any,
    provider_set: ProviderSet | None,
    locale: str,
    rag_store: RagStore | None = None,
    include_memory: bool = False,
) -> AsyncIterator[JsonDict]:
    disc_id = discussion_id or storage.new_discussion_id()
    clamped_ids, warnings = clamp_persona_ids(persona_ids, locale=locale)
    if warnings:
        yield {"type": "warning", "warnings": warnings, "discussion_id": disc_id}

    personas = storage.resolve_personas(plugin_data_dir, clamped_ids)
    if not personas:
        yield {"type": "error", "code": "personas_not_found", "discussion_id": disc_id}
        return

    stored = storage.load_discussion_messages(plugin_data_dir, disc_id)
    messages = list(stored or history)
    messages.append(
        {
            "role": "user",
            "content": message.strip(),
            "created_at": now_iso(),
        }
    )

    memory_text = ""
    if include_memory:
        memory_text = await _memory_context(rag_store, message, locale=locale)
    responses: list[JsonDict] = []

    for persona in personas:
        name = str(persona.get("name") or persona.get("id") or "")
        system_prompt = str(persona.get("system_prompt") or "")
        transcript_lines: list[str] = []
        for item in messages:
            role = item.get("role")
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            if role == "user":
                transcript_lines.append(f"Utilisateur : {content}")
            elif role == "persona":
                speaker = item.get("persona_name") or item.get("persona_id") or "Persona"
                transcript_lines.append(f"{speaker} : {content}")
        user_parts = ["Conversation en cours :\n" + "\n".join(transcript_lines)]
        if memory_text:
            user_parts.append(memory_text)
        user_parts.append("Réponds au dernier message de l'utilisateur, dans ton style.")
        content = await _run_persona_prompt(
            settings=settings,
            provider_set=provider_set,
            system_prompt=system_prompt,
            user_prompt=f"{system_prompt}\n\n" + "\n\n".join(user_parts),
            locale=locale,
        )
        entry = {
            "role": "persona",
            "persona_id": persona.get("id"),
            "persona_name": name,
            "role_label": persona.get("role"),
            "avatar_color": persona.get("avatar_color"),
            "content": content,
            "created_at": now_iso(),
        }
        responses.append(entry)
        yield {
            "type": "discuss_message",
            "discussion_id": disc_id,
            **entry,
        }

    messages.extend(responses)
    title = ", ".join(str(p.get("name") or "") for p in personas)
    storage.save_discussion_messages(
        plugin_data_dir,
        disc_id,
        messages,
        persona_ids=clamped_ids,
        title=title,
    )
    yield {"type": "done", "discussion_id": disc_id}
