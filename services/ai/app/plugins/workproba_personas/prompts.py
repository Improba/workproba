"""Construction des prompts personas (system / user, i18n, contexte non fiable)."""

from __future__ import annotations

from app.i18n import t


def build_panel_tools_notice(
    *,
    available_tools: list[str],
    degraded_tools: list[dict[str, object]],
    locale: str,
) -> str:
    """Notice des tools panel disponibles et dégradés (anti-hallucination)."""
    lines: list[str] = []
    header = t(locale, "personas.prompt.panel_tools.header")
    if header and not header.startswith("personas."):
        lines.append(header)
    if available_tools:
        available_line = t(
            locale,
            "personas.prompt.panel_tools.available",
            tools=", ".join(sorted(available_tools)),
        )
        if available_line and not available_line.startswith("personas."):
            lines.append(available_line)
    else:
        none_line = t(locale, "personas.prompt.panel_tools.none")
        if none_line and not none_line.startswith("personas."):
            lines.append(none_line)
    if degraded_tools:
        degraded_items: list[str] = []
        for entry in degraded_tools:
            connector_id = str(entry.get("connector_id") or "")
            tool = str(entry.get("tool") or "")
            reason = str(entry.get("reason") or "")
            degraded_items.append(f"{connector_id}/{tool} ({reason})")
        degraded_line = t(
            locale,
            "personas.prompt.panel_tools.degraded",
            items="; ".join(degraded_items),
        )
        if degraded_line and not degraded_line.startswith("personas."):
            lines.append(degraded_line)
    hallucination = t(locale, "personas.prompt.panel_tools.hallucination")
    if hallucination and not hallucination.startswith("personas."):
        lines.append(hallucination)
    return "\n".join(lines)


def build_persona_system_prompt(
    base_prompt: str,
    *,
    locale: str,
    mode: str | None = None,
) -> str:
    """Identité persona + règles stables dans le message system."""
    parts = [base_prompt.strip()]
    anti_injection = t(locale, "personas.prompt.anti_injection")
    respond_locale = t(locale, "personas.prompt.respond_in_locale")
    no_paste = t(locale, "personas.prompt.no_paste_identity")
    address_user = t(locale, "personas.prompt.address_user")
    if anti_injection and not anti_injection.startswith("personas."):
        parts.append(anti_injection)
    if respond_locale and not respond_locale.startswith("personas."):
        parts.append(respond_locale)
    if no_paste and not no_paste.startswith("personas."):
        parts.append(no_paste)
    if address_user and not address_user.startswith("personas."):
        parts.append(address_user)
    if mode == "operative":
        write_via_gate = t(locale, "personas.prompt.write_via_gate")
        if write_via_gate and not write_via_gate.startswith("personas."):
            parts.append(write_via_gate)
    platform_rules = t(locale, "personas.prompt.platform_rules_prevail")
    if platform_rules and not platform_rules.startswith("personas."):
        parts.append(platform_rules)
    return "\n\n".join(part for part in parts if part)


def format_cloud_user_identity_prompt(
    locale: str,
    *,
    current_user_email: str | None = None,
    current_user_display_name: str | None = None,
    current_user_ihora_id: str | None = None,
) -> str:
    """Identité cloud trusted (contexte session), jamais depuis untrusted."""
    identity_email: str | None = None
    identity_username: str | None = None

    context_email = (current_user_email or "").strip()
    if not context_email:
        return ""
    if "@" in context_email:
        identity_email = context_email
    else:
        identity_username = context_email

    display_name = (current_user_display_name or "").strip()
    lines: list[str] = []
    if identity_email:
        if not display_name:
            display_name = identity_email.split("@", 1)[0]
        lines.extend(
            [
                t(
                    locale,
                    "tools.cloud_current_user_identity",
                    email=identity_email,
                    display_name=display_name,
                ),
                t(
                    locale,
                    "tools.cloud_current_user_add_me_hint",
                    email=identity_email,
                    display_name=display_name,
                ),
            ]
        )
    else:
        assert identity_username is not None
        if not display_name:
            display_name = identity_username
        lines.extend(
            [
                t(
                    locale,
                    "tools.cloud_current_user_identity_username_only",
                    display_name=display_name,
                    username=identity_username,
                ),
                t(locale, "tools.cloud_current_user_username_only_hint"),
            ]
        )

    ihora_id = (current_user_ihora_id or "").strip()
    if ihora_id:
        lines.append(
            t(
                locale,
                "tools.cloud_current_user_ihora_id",
                user_id=ihora_id,
            )
        )
    return "\n".join(lines)


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
    directive: bool = False,
) -> str:
    label_key = (
        "personas.prompt.specialist.directive_label"
        if directive
        else "personas.prompt.opinion.question_label"
    )
    parts = [f"{t(locale, label_key)} : {question.strip()}"]
    wrapped = wrap_untrusted_context(context, locale=locale)
    if wrapped:
        parts.append(
            f"{t(locale, 'personas.prompt.opinion.context_label')} :\n{wrapped}",
        )
    if memory_text.strip():
        parts.append(memory_text.strip())
    parts.append(t(locale, "personas.prompt.opinion.format"))
    return "\n\n".join(parts)


def build_operative_user_prompt(
    *,
    directive: str,
    context: str,
    memory_text: str,
    locale: str,
) -> str:
    parts = [
        f"{t(locale, 'personas.prompt.specialist.directive_label')} : {directive.strip()}",
    ]
    wrapped = wrap_untrusted_context(context, locale=locale)
    if wrapped:
        parts.append(
            f"{t(locale, 'personas.prompt.operative.context_label')} :\n{wrapped}",
        )
    if memory_text.strip():
        parts.append(memory_text.strip())
    parts.append(t(locale, "personas.prompt.operative.format"))
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
