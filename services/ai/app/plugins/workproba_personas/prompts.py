"""Construction des prompts personas (system / user, i18n, contexte non fiable)."""

from __future__ import annotations

from app.i18n import t


def build_persona_system_prompt(base_prompt: str, *, locale: str) -> str:
    """Identité persona + règles stables dans le message system."""
    parts = [base_prompt.strip()]
    anti_injection = t(locale, "personas.prompt.anti_injection")
    respond_locale = t(locale, "personas.prompt.respond_in_locale")
    if anti_injection and not anti_injection.startswith("personas."):
        parts.append(anti_injection)
    if respond_locale and not respond_locale.startswith("personas."):
        parts.append(respond_locale)
    return "\n\n".join(part for part in parts if part)


def wrap_untrusted_context(context: str, *, locale: str) -> str:
    if not context.strip():
        return ""
    header = t(locale, "personas.prompt.untrusted_header")
    return f"{header}\n<untrusted>\n{context.strip()}\n</untrusted>"


def build_opinion_user_prompt(
    *,
    question: str,
    context: str,
    memory_text: str,
    locale: str,
) -> str:
    parts = [f"{t(locale, 'personas.prompt.opinion.question_label')} : {question.strip()}"]
    wrapped = wrap_untrusted_context(context, locale=locale)
    if wrapped:
        parts.append(
            f"{t(locale, 'personas.prompt.opinion.context_label')} :\n{wrapped}",
        )
    if memory_text.strip():
        parts.append(memory_text.strip())
    parts.append(t(locale, "personas.prompt.opinion.format"))
    return "\n\n".join(parts)


def format_discuss_transcript_line(
    *,
    role: str,
    content: str,
    persona_name: str | None,
    locale: str,
) -> str:
    if role == "user":
        label = t(locale, "personas.prompt.discuss.transcript_user")
        return f"{label} : {content}"
    if role == "persona":
        name = persona_name or "Persona"
        label = t(locale, "personas.prompt.discuss.transcript_persona", name=name)
        return f"{label} : {content}"
    return content


def build_discuss_user_prompt(
    *,
    transcript_lines: list[str],
    context: str,
    memory_text: str,
    locale: str,
) -> str:
    parts = [
        f"{t(locale, 'personas.prompt.discuss.active_header')} :\n"
        + "\n".join(transcript_lines),
    ]
    wrapped = wrap_untrusted_context(context, locale=locale)
    if wrapped:
        parts.append(
            f"{t(locale, 'personas.prompt.discuss.main_context_label')} :\n{wrapped}",
        )
    if memory_text.strip():
        parts.append(memory_text.strip())
    parts.append(t(locale, "personas.prompt.discuss.hierarchy"))
    parts.append(t(locale, "personas.prompt.discuss.reply"))
    return "\n\n".join(parts)


def build_meeting_user_prompt(
    *,
    topic: str,
    context: str,
    memory_text: str,
    history: str,
    round_no: int,
    locale: str,
) -> str:
    parts = [f"{t(locale, 'personas.prompt.meeting.topic_label')} : {topic.strip()}"]
    wrapped = wrap_untrusted_context(context, locale=locale)
    if wrapped:
        parts.append(
            f"{t(locale, 'personas.prompt.meeting.context_label')} :\n{wrapped}",
        )
    if memory_text.strip():
        parts.append(memory_text.strip())
    if history.strip():
        parts.append(
            f"{t(locale, 'personas.prompt.meeting.history_label')} :\n{history.strip()}",
        )
    if round_no == 1:
        parts.append(t(locale, "personas.prompt.meeting.round1"))
    else:
        parts.append(t(locale, "personas.prompt.meeting.round_n"))
    return "\n\n".join(parts)


def build_facilitator_system_prompt(*, locale: str) -> str:
    return t(locale, "personas.prompt.facilitator.system")


def build_facilitator_synthesis_prompt(*, topic: str, history: str, locale: str) -> str:
    return t(
        locale,
        "personas.prompt.facilitator.synthesis",
        topic=topic.strip(),
        history=history.strip(),
    )
