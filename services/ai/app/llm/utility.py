from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError
from pydantic_ai import Agent

from app.config import ProviderName
from app.i18n import DEFAULT_LOCALE, t
from app.llm.config import build_model, build_model_settings
from app.llm.provider_sets import resolve_chat_from_set
from app.schemas import (
    ChatMessage,
    LLMProviderConfig,
    ProviderSet,
    UtilitySummarizeRequest,
    UtilitySummarizeResponse,
    UtilityTitleRequest,
    UtilityTitleResponse,
)


def title_system_prompt(locale: str = DEFAULT_LOCALE) -> str:
    return t(locale, "utility.title_system_prompt")


def summary_system_prompt(locale: str = DEFAULT_LOCALE) -> str:
    return t(locale, "utility.summary_system_prompt")


TITLE_SYSTEM_PROMPT = title_system_prompt()
SUMMARY_SYSTEM_PROMPT = summary_system_prompt()


def resolve_utility_config(
    utility: LLMProviderConfig | None,
    chat: LLMProviderConfig | None,
    settings: Any,
    *,
    provider_set: ProviderSet | None = None,
    cloud_plugin_data_dir: str | Path | None = None,
) -> LLMProviderConfig:
    """Résout la config utilitaire.

    Si ``provider_set`` est fourni (ex. Improba Cloud), on résout via le set
    pour injecter DeviceBearer + base URL du proxy — jamais l'API publique.
    """
    if provider_set is not None:
        return resolve_chat_from_set(
            provider_set,
            cloud_plugin_data_dir=cloud_plugin_data_dir,
        )
    if utility is not None:
        return utility
    if chat is not None:
        return chat

    settings_config = _utility_config_from_settings(settings)
    if settings_config is not None:
        return settings_config

    raise ValueError(
        "Aucune configuration LLM utilitaire disponible. Fournissez utility_llm_config, "
        "llm_provider_config, provider_set ou les variables LLM_UTILITY_PROVIDER et "
        "LLM_UTILITY_MODEL."
    )


async def generate_title(req: UtilityTitleRequest, settings: Any) -> UtilityTitleResponse:
    locale = req.locale
    config = resolve_utility_config(
        req.utility_llm_config,
        req.llm_provider_config,
        settings,
        provider_set=req.provider_set,
        cloud_plugin_data_dir=req.cloud_plugin_data_dir,
    )
    agent = Agent(
        build_model(config),
        system_prompt=title_system_prompt(locale),
        output_type=str,
        model_settings=build_model_settings(config),
    )
    result = await agent.run(
        f"{t(locale, 'utility.user_message_label')}\n"
        f"{req.first_user_message.strip()}\n\n"
        f"{t(locale, 'utility.assistant_reply_label')}\n"
        f"{req.first_assistant_reply.strip()}\n\n"
        f"{t(locale, 'utility.title_prompt_suffix')}"
    )
    return UtilityTitleResponse(
        title=_clean_title(_result_output(result), locale=locale)
    )


async def summarize_conversation(
    req: UtilitySummarizeRequest,
    settings: Any,
) -> UtilitySummarizeResponse:
    locale = req.locale
    config = resolve_utility_config(
        req.utility_llm_config,
        req.llm_provider_config,
        settings,
        provider_set=req.provider_set,
        cloud_plugin_data_dir=req.cloud_plugin_data_dir,
    )
    agent = Agent(
        build_model(config),
        system_prompt=summary_system_prompt(locale),
        output_type=str,
        model_settings=build_model_settings(config),
    )
    result = await agent.run(_summary_prompt(req, locale))
    input_tokens, output_tokens, _ = extract_usage_tokens(result)
    return UtilitySummarizeResponse(
        summary=_result_output(result).strip(),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def extract_usage_tokens(source: Any) -> tuple[int | None, int | None, int | None]:
    usage = _read_usage(source)
    if usage is None:
        return None, None, None
    return (
        _int_or_none(getattr(usage, "input_tokens", None)),
        _int_or_none(getattr(usage, "output_tokens", None)),
        _int_or_none(getattr(usage, "total_tokens", None)),
    )


def _utility_config_from_settings(settings: Any) -> LLMProviderConfig | None:
    provider = _strip_or_none(getattr(settings, "llm_utility_provider", None))
    model = _strip_or_none(getattr(settings, "llm_utility_model", None))
    base_url = _strip_or_none(getattr(settings, "llm_utility_base_url", None))
    api_key = _strip_or_none(getattr(settings, "llm_utility_api_key", None))

    if not any((provider, model, base_url, api_key)):
        return None
    if not provider or not model:
        raise ValueError(
            "Configuration LLM utilitaire incomplète : LLM_UTILITY_PROVIDER et "
            "LLM_UTILITY_MODEL sont requis ensemble."
        )

    try:
        return LLMProviderConfig(
            provider=cast(ProviderName, provider),
            model=model,
            base_url=base_url,
            api_key=api_key,
        )
    except ValidationError as exc:
        raise ValueError(f"Configuration LLM utilitaire invalide : {exc}") from exc


def _summary_prompt(req: UtilitySummarizeRequest, locale: str) -> str:
    parts: list[str] = []
    focus = (req.focus or "").strip()
    if focus:
        parts.append(t(locale, "utility.focus_prefix", focus=focus))
    prior_summary = (req.prior_summary or "").strip()
    if prior_summary:
        parts.append(
            t(locale, "utility.compaction_prior_summary", summary=prior_summary)
        )
    parts.append(t(locale, "utility.transcript_label"))
    parts.append(_format_transcript(req.messages, locale))
    return "\n\n".join(parts)


def _format_transcript(messages: list[ChatMessage], locale: str) -> str:
    rendered: list[str] = []
    for index, message in enumerate(messages, start=1):
        chunks: list[str] = []
        if message.content:
            chunks.append(message.content.strip())
        if message.thinking:
            chunks.append(
                t(
                    locale,
                    "utility.thinking_label",
                    thinking=message.thinking.strip(),
                )
            )
        if message.tool_calls:
            calls = [
                (
                    f"{tool.name}("
                    f"{json.dumps(tool.arguments, ensure_ascii=False, sort_keys=True)})"
                )
                for tool in message.tool_calls
            ]
            chunks.append(
                t(locale, "utility.tool_calls_label", calls=", ".join(calls))
            )
        content = (
            "\n".join(chunk for chunk in chunks if chunk)
            or t(locale, "utility.empty_transcript")
        )
        rendered.append(
            t(
                locale,
                "utility.role_prefix",
                index=index,
                role=message.role,
                content=content,
            )
        )
    return "\n".join(rendered)


def _clean_title(value: str, *, locale: str = DEFAULT_LOCALE) -> str:
    title = re.sub(r"\s+", " ", value.strip())
    while len(title) >= 2 and title[0] == title[-1] and title[0] in {"'", '"'}:
        title = title[1:-1].strip()
    title = title[:60].strip()
    title = title.rstrip(" .!?:;,")
    return title or t(locale, "utility.default_title")


def _result_output(result: Any) -> str:
    output = getattr(result, "output", result)
    return output if isinstance(output, str) else str(output)


def _read_usage(source: Any) -> Any | None:
    usage_attr = getattr(source, "usage", None)
    if usage_attr is None:
        return None
    try:
        return usage_attr() if callable(usage_attr) else usage_attr
    except Exception:
        return None


def _int_or_none(value: Any) -> int | None:
    return int(value) if value is not None else None


def _strip_or_none(value: Any) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None
