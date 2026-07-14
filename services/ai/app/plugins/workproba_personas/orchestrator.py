"""Orchestration LLM des modes personas (avis, réunion, discussion)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from pydantic_ai import Agent

from app.i18n import t
from app.llm.config import build_model, build_model_settings, resolve_llm_config
from app.plugins.workproba_personas import manifest, prompts, storage
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


def _build_agent(
    settings: Any,
    provider_set: ProviderSet | None,
    system_prompt: str,
) -> Agent[None, str]:
    llm_config = resolve_llm_config(None, settings, provider_set=provider_set)
    return Agent(
        build_model(llm_config),
        system_prompt=system_prompt,
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
    full_system = prompts.build_persona_system_prompt(system_prompt, locale=locale)
    agent = _build_agent(settings, provider_set, full_system)
    result = await agent.run(user_prompt, message_history=[], deps=None)
    output = getattr(result, "output", result)
    return output.strip() if isinstance(output, str) else str(output).strip()


def _persona_opinion_entry(persona: JsonDict, content: str, *, memory_text: str) -> JsonDict:
    name = str(persona.get("name") or persona.get("id") or "")
    return {
        "persona_id": persona.get("id"),
        "persona_name": name,
        "role": persona.get("role"),
        "avatar_color": persona.get("avatar_color"),
        "avatar_icon": persona.get("avatar_icon"),
        "content": content,
        "memory_citations": bool(memory_text),
    }


async def _run_personas_parallel(
    personas: list[JsonDict],
    *,
    settings: Any,
    provider_set: ProviderSet | None,
    user_prompt: str,
    locale: str,
) -> list[tuple[JsonDict, str]]:
    """Exécute les appels persona indépendants en parallèle (ordre préservé à la sortie)."""

    async def _one(persona: JsonDict) -> tuple[JsonDict, str]:
        system_prompt = str(persona.get("system_prompt") or "")
        content = await _run_persona_prompt(
            settings=settings,
            provider_set=provider_set,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            locale=locale,
        )
        return persona, content

    async with asyncio.TaskGroup() as group:
        tasks = [group.create_task(_one(persona)) for persona in personas]
    return [task.result() for task in tasks]


async def _stream_personas_parallel(
    personas: list[JsonDict],
    *,
    settings: Any,
    provider_set: ProviderSet | None,
    user_prompt: str,
    locale: str,
) -> AsyncIterator[tuple[JsonDict, str]]:
    """Exécute les personas en parallèle et yield au fur et à mesure des réponses."""

    async def _one(persona: JsonDict) -> tuple[JsonDict, str]:
        system_prompt = str(persona.get("system_prompt") or "")
        content = await _run_persona_prompt(
            settings=settings,
            provider_set=provider_set,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            locale=locale,
        )
        return persona, content

    tasks = [asyncio.create_task(_one(persona)) for persona in personas]
    try:
        for done in asyncio.as_completed(tasks):
            yield await done
    except Exception:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


def _discuss_transcript_lines(messages: list[JsonDict], *, locale: str) -> list[str]:
    lines: list[str] = []
    for item in messages:
        role = item.get("role")
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        if role not in {"user", "persona"}:
            continue
        speaker = item.get("persona_name") if role == "persona" else None
        lines.append(
            prompts.format_discuss_transcript_line(
                role=str(role),
                content=content,
                persona_name=str(speaker) if speaker else None,
                locale=locale,
            )
        )
    return lines


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
    user_prompt = prompts.build_opinion_user_prompt(
        question=question,
        context=context,
        memory_text=memory_text,
        locale=locale,
    )
    opinions: list[JsonDict] = []
    parallel_results = await _run_personas_parallel(
        personas,
        settings=settings,
        provider_set=provider_set,
        user_prompt=user_prompt,
        locale=locale,
    )
    for persona, content in parallel_results:
        opinions.append(_persona_opinion_entry(persona, content, memory_text=memory_text))
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
    user_prompt = prompts.build_opinion_user_prompt(
        question=question,
        context=context,
        memory_text=memory_text,
        locale=locale,
    )
    async for persona, content in _stream_personas_parallel(
        personas,
        settings=settings,
        provider_set=provider_set,
        user_prompt=user_prompt,
        locale=locale,
    ):
        yield {
            "type": "persona_opinion",
            **_persona_opinion_entry(persona, content, memory_text=memory_text),
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
            user_prompt = prompts.build_meeting_user_prompt(
                topic=topic,
                context=context,
                memory_text=memory_text,
                history=history,
                round_no=round_no,
                locale=locale,
            )
            content = await _run_persona_prompt(
                settings=settings,
                provider_set=provider_set,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                locale=locale,
            )
            turn = {
                "round": round_no,
                "persona_id": persona.get("id"),
                "persona_name": name,
                "role": persona.get("role"),
                "avatar_color": persona.get("avatar_color"),
                "avatar_icon": persona.get("avatar_icon"),
                "content": content,
            }
            turns.append(turn)
            yield {"type": "meeting_turn", "meeting_id": resolved_meeting_id, **turn}

    synthesizer = personas[-1]
    yield {
        "type": "meeting_facilitator",
        "meeting_id": resolved_meeting_id,
        "round": 0,
        "label": t(locale, "personas.meeting.facilitator.synthesis"),
    }
    summary_system = prompts.build_facilitator_system_prompt(locale=locale)
    meeting_history = _format_meeting_history(turns)
    summary_user = prompts.build_facilitator_synthesis_prompt(
        topic=topic,
        history=meeting_history,
        locale=locale,
    )
    summary = await _run_persona_prompt(
        settings=settings,
        provider_set=provider_set,
        system_prompt=summary_system,
        user_prompt=summary_user,
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
            "persona_id": synthesizer.get("id"),
            "persona_name": synthesizer.get("name"),
            "title": t(locale, "personas.meeting_summary_title"),
            "content": summary,
        },
        "warnings": warnings,
    }
    storage.save_meeting_transcript(plugin_data_dir, resolved_meeting_id, transcript)
    yield {
        "type": "meeting_summary",
        "meeting_id": resolved_meeting_id,
        "persona_id": synthesizer.get("id"),
        "persona_name": synthesizer.get("name"),
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
    context: str = "",
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
        memory_text = await _memory_context(rag_store, f"{message}\n{context}", locale=locale)
    responses: list[JsonDict] = []
    working_messages = list(messages)

    for persona in personas:
        name = str(persona.get("name") or persona.get("id") or "")
        system_prompt = str(persona.get("system_prompt") or "")
        transcript_lines = _discuss_transcript_lines(working_messages, locale=locale)
        user_prompt = prompts.build_discuss_user_prompt(
            transcript_lines=transcript_lines,
            context=context,
            memory_text=memory_text,
            locale=locale,
        )
        content = await _run_persona_prompt(
            settings=settings,
            provider_set=provider_set,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            locale=locale,
        )
        entry = {
            "role": "persona",
            "persona_id": persona.get("id"),
            "persona_name": name,
            "role_label": persona.get("role"),
            "avatar_color": persona.get("avatar_color"),
            "avatar_icon": persona.get("avatar_icon"),
            "content": content,
            "created_at": now_iso(),
        }
        responses.append(entry)
        working_messages.append(entry)
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
