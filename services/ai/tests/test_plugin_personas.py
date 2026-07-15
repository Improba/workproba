"""Tests plugin personas (storage, orchestration, outils, plafonds)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel

from app.agent.tools import ToolDeps, ToolContext, build_agent
from app.limits import DEFAULT_LIMITS
from app.plugins.workproba_personas import PLUGIN_ID, manifest, orchestrator, storage
from app.sandbox.runner import SandboxRunner

from conftest import FakeProjectClient


@pytest.fixture
def plugin_dir(tmp_path: Path) -> Path:
    path = tmp_path / "plugins" / "workproba.personas"
    path.mkdir(parents=True)
    return path


@pytest.fixture(autouse=True)
def _mock_persona_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run(
        *,
        settings: Any,
        provider_set: Any,
        system_prompt: str,
        user_prompt: str,
        locale: str,
    ) -> str:
        _ = (settings, provider_set, system_prompt, locale)
        if "synthèse" in user_prompt.lower():
            return "Synthèse simulée."
        return "Intervention simulée."

    monkeypatch.setattr(orchestrator, "_run_persona_prompt", fake_run)


def test_builtin_set_has_six_personas() -> None:
    persona_set = storage.builtin_persona_set()
    assert persona_set["id"] == "default"
    assert len(persona_set["personas"]) == 6
    names = {persona["name"] for persona in persona_set["personas"]}
    assert names == {"RH", "Juriste", "Comptable / DAF", "Ingénieur", "Scientifique", "Designer"}
    icons = {persona["avatar_icon"] for persona in persona_set["personas"]}
    assert icons == {"users", "scale", "calculator", "code", "flask-conical", "palette"}


def test_resolve_personas_from_builtin(plugin_dir: Path) -> None:
    personas = storage.resolve_personas(plugin_dir, ["01", "06"])
    assert [persona["name"] for persona in personas] == ["RH", "Designer"]


@pytest.mark.asyncio
async def test_generate_opinions(plugin_dir: Path) -> None:
    opinions, warnings = await orchestrator.generate_opinions(
        plugin_data_dir=plugin_dir,
        persona_ids=["01", "03"],
        question="Ce contrat est-il clair ?",
        context="Brouillon v2",
        settings=object(),
        provider_set=None,
        locale="fr",
        rag_store=None,
    )
    assert len(opinions) == 2
    assert opinions[0]["persona_name"] == "RH"
    assert opinions[0]["content"] == "Intervention simulée."
    assert warnings == []


@pytest.mark.asyncio
async def test_stream_ask_injects_memory_context(plugin_dir: Path) -> None:
    captured_queries: list[str] = []

    class FakeRagStore:
        async def search_combined(self, *, query: str, limit: int = 8) -> list[dict[str, str]]:
            captured_queries.append(query)
            return [
                {
                    "title": "Budget Q2",
                    "content": "Le budget RH est validé à 120k€.",
                    "document_id": "mem-1",
                }
            ]

    events = [
        event
        async for event in orchestrator.stream_ask(
            plugin_data_dir=plugin_dir,
            persona_ids=["01"],
            question="Quel budget ?",
            context="",
            settings=object(),
            provider_set=None,
            locale="fr",
            rag_store=FakeRagStore(),  # type: ignore[arg-type]
        )
    ]
    assert captured_queries == ["Quel budget ?\n"]
    opinion = next(event for event in events if event.get("type") == "persona_opinion")
    assert opinion.get("memory_cited") is True
    assert isinstance(opinion.get("memory_citations"), list)
    assert len(opinion.get("memory_citations") or []) >= 1


@pytest.mark.asyncio
async def test_stream_ask_without_rag_store_skips_memory(plugin_dir: Path) -> None:
    events = [
        event
        async for event in orchestrator.stream_ask(
            plugin_data_dir=plugin_dir,
            persona_ids=["01"],
            question="Avis ?",
            context="",
            settings=object(),
            provider_set=None,
            locale="fr",
            rag_store=None,
        )
    ]
    opinion = next(event for event in events if event.get("type") == "persona_opinion")
    assert opinion.get("memory_cited") is False
    assert opinion.get("memory_citations") == []


@pytest.mark.asyncio
async def test_stream_ask_emits_one_block_per_persona(plugin_dir: Path) -> None:
    events = [
        event
        async for event in orchestrator.stream_ask(
            plugin_data_dir=plugin_dir,
            persona_ids=["01"],
            question="Avis ?",
            context="",
            settings=object(),
            provider_set=None,
            locale="fr",
        )
    ]
    types = [event["type"] for event in events]
    assert "persona_opinion" in types
    assert types[-1] == "done"


@pytest.mark.asyncio
async def test_stream_meeting_saves_transcript(plugin_dir: Path) -> None:
    events = [
        event
        async for event in orchestrator.stream_meeting(
            plugin_data_dir=plugin_dir,
            persona_ids=["01", "03"],
            topic="Validation RH",
            rounds=2,
            context="",
            settings=object(),
            provider_set=None,
            locale="fr",
        )
    ]
    meeting_id = next(
        event["meeting_id"] for event in events if event.get("type") == "meeting_started"
    )
    transcript_path = plugin_dir / "meetings" / meeting_id / "transcript.json"
    assert transcript_path.is_file()
    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    assert transcript["topic"] == "Validation RH"
    assert len(transcript["turns"]) == 4
    assert transcript["summary"]["content"]


@pytest.mark.asyncio
async def test_stream_discuss_persists_messages(plugin_dir: Path) -> None:
    events = [
        event
        async for event in orchestrator.stream_discuss(
            plugin_data_dir=plugin_dir,
            persona_ids=["04"],
            message="Que penses-tu de cette spec ?",
            history=[],
            discussion_id=None,
            settings=object(),
            provider_set=None,
            locale="fr",
        )
    ]
    discussion_id = next(event["discussion_id"] for event in events if event.get("type") == "done")
    messages_path = plugin_dir / "discussions" / discussion_id / "messages.json"
    assert messages_path.is_file()
    payload = json.loads(messages_path.read_text(encoding="utf-8"))
    assert payload["messages"][0]["role"] == "user"
    assert payload["messages"][1]["role"] == "persona"


def test_rounds_and_personas_capped() -> None:
    ids, id_warnings = orchestrator.clamp_persona_ids(
        ["01", "02", "03", "04", "05", "06"],
        locale="fr",
    )
    assert len(ids) == manifest.MAX_PERSONAS
    assert id_warnings

    rounds, round_warnings = orchestrator.clamp_rounds(99, locale="fr")
    assert rounds == manifest.MAX_ROUNDS
    assert round_warnings


def test_plugin_tools_hidden_without_active_plugins() -> None:
    agent = build_agent(TestModel())
    names = sorted(agent._function_toolset.tools.keys())
    assert "ask_personas" not in names
    assert "simulate_meeting" not in names


def test_plugin_tools_registered_when_active() -> None:
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_ID])
    names = sorted(agent._function_toolset.tools.keys())
    assert "ask_personas" in names
    assert "simulate_meeting" in names


@pytest.mark.asyncio
async def test_ask_personas_tool_returns_opinions(plugin_dir: Path) -> None:
    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s1",
            documents=[],
            plugin_data_dir=plugin_dir,
            locale="fr",
            active_plugins=[PLUGIN_ID],
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
    )
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_ID])
    tool = agent._function_toolset.tools["ask_personas"]
    ctx = RunContext(deps=deps, model=TestModel(), usage=None, prompt=None, tool_call_id="tc1")
    result = await tool.function(ctx, persona_ids=["01"], question="Ce process est-il simple ?")
    assert result["display"] == "persona_opinion_card"
    assert len(result["opinions"]) == 1


@pytest.mark.asyncio
async def test_simulate_meeting_tool_returns_open_event(plugin_dir: Path) -> None:
    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s1",
            documents=[],
            plugin_data_dir=plugin_dir,
            locale="fr",
            active_plugins=[PLUGIN_ID],
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
    )
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_ID])
    tool = agent._function_toolset.tools["simulate_meeting"]
    ctx = RunContext(deps=deps, model=TestModel(), usage=None, prompt=None, tool_call_id="tc2")
    result = await tool.function(
        ctx,
        persona_ids=["01", "06"],
        topic="Revue contrat",
        rounds=3,
    )
    assert result["action"] == "open_meeting_view"
    assert result["rounds"] == 3
    assert result["meeting_id"]


@pytest.mark.asyncio
async def test_stream_meeting_reuses_meeting_id_when_passed(plugin_dir: Path) -> None:
    custom_id = "mtg_custom123456"
    events = [
        event
        async for event in orchestrator.stream_meeting(
            plugin_data_dir=plugin_dir,
            persona_ids=["01"],
            topic="Sujet test",
            rounds=1,
            context="",
            settings=object(),
            provider_set=None,
            locale="fr",
            meeting_id=custom_id,
        )
    ]
    meeting_ids = {event.get("meeting_id") for event in events if event.get("meeting_id")}
    assert meeting_ids == {custom_id}
    assert (plugin_dir / "meetings" / custom_id / "transcript.json").is_file()


@pytest.mark.asyncio
async def test_stream_meeting_done_carries_meeting_id(plugin_dir: Path) -> None:
    events = [
        event
        async for event in orchestrator.stream_meeting(
            plugin_data_dir=plugin_dir,
            persona_ids=["01"],
            topic="Sujet",
            rounds=1,
            context="",
            settings=object(),
            provider_set=None,
            locale="fr",
        )
    ]
    done = next(event for event in events if event["type"] == "done")
    started = next(event for event in events if event["type"] == "meeting_started")
    assert done["meeting_id"] == started["meeting_id"]


@pytest.mark.asyncio
async def test_stream_meeting_started_before_first_turn(plugin_dir: Path) -> None:
    events = [
        event
        async for event in orchestrator.stream_meeting(
            plugin_data_dir=plugin_dir,
            persona_ids=["01"],
            topic="Ordre",
            rounds=1,
            context="",
            settings=object(),
            provider_set=None,
            locale="fr",
        )
    ]
    types = [event["type"] for event in events]
    started_idx = types.index("meeting_started")
    facilitator_idx = types.index("meeting_facilitator")
    turn_idx = types.index("meeting_turn")
    assert started_idx < facilitator_idx < turn_idx


@pytest.mark.asyncio
async def test_stream_meeting_emits_facilitator_events(plugin_dir: Path) -> None:
    events = [
        event
        async for event in orchestrator.stream_meeting(
            plugin_data_dir=plugin_dir,
            persona_ids=["01", "03"],
            topic="Facilitation",
            rounds=2,
            context="",
            settings=object(),
            provider_set=None,
            locale="fr",
        )
    ]
    facilitator_events = [event for event in events if event["type"] == "meeting_facilitator"]
    assert len(facilitator_events) == 3
    assert facilitator_events[0]["round"] == 1
    assert facilitator_events[0]["label"]
    assert facilitator_events[1]["round"] == 2
    assert facilitator_events[2]["round"] == 0
    assert "Synthèse" in facilitator_events[2]["label"]


@pytest.mark.asyncio
async def test_stream_meeting_summary_includes_persona_name(plugin_dir: Path) -> None:
    events = [
        event
        async for event in orchestrator.stream_meeting(
            plugin_data_dir=plugin_dir,
            persona_ids=["01", "06"],
            topic="Synthèse",
            rounds=1,
            context="",
            settings=object(),
            provider_set=None,
            locale="fr",
        )
    ]
    summary = next(event for event in events if event["type"] == "meeting_summary")
    assert summary["persona_name"] == "Designer"
    assert summary["content"]


@pytest.mark.asyncio
async def test_stream_discuss_without_include_memory_skips_rag(plugin_dir: Path) -> None:
    captured_queries: list[str] = []

    class FakeRagStore:
        async def search_combined(self, *, query: str, limit: int = 8) -> list[dict[str, str]]:
            captured_queries.append(query)
            return [{"title": "Doc", "content": "Info", "document_id": "d1"}]

    events = [
        event
        async for event in orchestrator.stream_discuss(
            plugin_data_dir=plugin_dir,
            persona_ids=["04"],
            message="Question ?",
            history=[],
            discussion_id=None,
            settings=object(),
            provider_set=None,
            locale="fr",
            rag_store=FakeRagStore(),  # type: ignore[arg-type]
            include_memory=False,
        )
    ]
    assert captured_queries == []
    assert any(event["type"] == "done" for event in events)


@pytest.mark.asyncio
async def test_stream_discuss_with_include_memory_uses_rag(plugin_dir: Path) -> None:
    captured_queries: list[str] = []

    class FakeRagStore:
        async def search_combined(self, *, query: str, limit: int = 8) -> list[dict[str, str]]:
            captured_queries.append(query)
            return [{"title": "Doc", "content": "Info", "document_id": "d1"}]

    events = [
        event
        async for event in orchestrator.stream_discuss(
            plugin_data_dir=plugin_dir,
            persona_ids=["04"],
            message="Question mémoire ?",
            history=[],
            discussion_id=None,
            settings=object(),
            provider_set=None,
            locale="fr",
            rag_store=FakeRagStore(),  # type: ignore[arg-type]
            include_memory=True,
        )
    ]
    assert captured_queries[0].startswith("Question mémoire ?")
    assert any(event["type"] == "discuss_message" for event in events)


@pytest.mark.asyncio
async def test_stream_discuss_injects_main_conversation_context(
    plugin_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_system: list[str] = []
    captured_user: list[str] = []

    async def fake_run(
        *,
        settings: Any,
        provider_set: Any,
        system_prompt: str,
        user_prompt: str,
        locale: str,
    ) -> str:
        _ = (settings, provider_set, locale)
        captured_system.append(system_prompt)
        captured_user.append(user_prompt)
        return "Réponse simulée."

    monkeypatch.setattr(orchestrator, "_run_persona_prompt", fake_run)

    events = [
        event
        async for event in orchestrator.stream_discuss(
            plugin_data_dir=plugin_dir,
            persona_ids=["04"],
            message="Que penses-tu ?",
            history=[],
            discussion_id=None,
            context="Utilisateur : Je fais mon CV\nAssistant : D'accord",
            settings=object(),
            provider_set=None,
            locale="fr",
        )
    ]
    assert any(event["type"] == "done" for event in events)
    assert captured_system
    assert captured_user
    assert "ingénieur" in captured_system[0].lower()
    assert "<untrusted>" in captured_user[0]
    assert "Je fais mon CV" in captured_user[0]
    assert "Priorité" in captured_user[0]


def test_list_and_get_meetings(plugin_dir: Path) -> None:
    meeting_id = "mtg_listtest01"
    storage.save_meeting_transcript(
        plugin_dir,
        meeting_id,
        {
            "id": meeting_id,
            "topic": "Revue",
            "rounds": 2,
            "persona_ids": ["01", "03"],
            "created_at": "2026-07-11T10:00:00+00:00",
            "turns": [{"round": 1, "persona_id": "01", "content": "Avis"}],
            "summary": {"content": "Synthèse"},
        },
    )
    meetings = storage.list_meetings(plugin_dir)
    assert len(meetings) == 1
    assert meetings[0]["meeting_id"] == meeting_id
    assert meetings[0]["topic"] == "Revue"

    detail = storage.get_meeting(plugin_dir, meeting_id)
    assert detail is not None
    assert detail["meeting_id"] == meeting_id
    assert len(detail["transcript"]) == 1
    assert storage.get_meeting(plugin_dir, "missing") is None


def test_list_and_get_discussions(plugin_dir: Path) -> None:
    discussion_id = "disc_listtest01"
    storage.save_discussion_messages(
        plugin_dir,
        discussion_id,
        [
            {"role": "user", "content": "Bonjour", "created_at": "2026-07-11T10:00:00+00:00"},
            {"role": "persona", "persona_id": "04", "content": "Salut", "created_at": "2026-07-11T10:01:00+00:00"},
        ],
        persona_ids=["04"],
        title="Karim",
    )
    discussions = storage.list_discussions(plugin_dir)
    assert len(discussions) == 1
    assert discussions[0]["discussion_id"] == discussion_id
    assert discussions[0]["last_message_at"] == "2026-07-11T10:01:00+00:00"

    detail = storage.get_discussion(plugin_dir, discussion_id)
    assert detail is not None
    assert detail["discussion_id"] == discussion_id
    assert detail["last_message_at"] == "2026-07-11T10:01:00+00:00"
    assert len(detail["messages"]) == 2
    assert storage.get_discussion(plugin_dir, "missing") is None


def test_upsert_and_delete_custom_sets(plugin_dir: Path) -> None:
    saved = storage.upsert_custom_set(
        plugin_dir,
        {
            "name": "Mon équipe",
            "personas": [{"id": "01", "name": "Sylvie", "role": "RH", "avatar_color": "#fff"}],
        },
    )
    assert saved["id"].startswith("custom_")
    assert saved["name"] == "Mon équipe"
    assert len(saved["personas"]) == 1

    updated = storage.upsert_custom_set(
        plugin_dir,
        {
            "id": saved["id"],
            "name": "Équipe revue",
            "personas": [
                {"id": "01", "name": "Sylvie", "role": "RH", "avatar_color": "#fff"},
                {"id": "03", "name": "Marc", "role": "DSI", "avatar_color": "#000"},
            ],
        },
    )
    assert updated["id"] == saved["id"]
    assert updated["name"] == "Équipe revue"
    assert len(updated["personas"]) == 2

    sets = storage.list_sets(plugin_dir)
    custom_ids = [item["id"] for item in sets if item["id"] != storage.BUILTIN_SET_ID]
    assert saved["id"] in custom_ids

    assert storage.delete_custom_set(plugin_dir, saved["id"]) is True
    assert storage.delete_custom_set(plugin_dir, saved["id"]) is False
    assert storage.delete_custom_set(plugin_dir, storage.BUILTIN_SET_ID) is False


def test_get_meeting_includes_summary(plugin_dir: Path) -> None:
    meeting_id = "mtg_summary01"
    storage.save_meeting_transcript(
        plugin_dir,
        meeting_id,
        {
            "id": meeting_id,
            "topic": "Revue",
            "rounds": 1,
            "persona_ids": ["01"],
            "created_at": "2026-07-11T10:00:00+00:00",
            "turns": [{"round": 1, "persona_id": "01", "persona_name": "Sylvie", "content": "Avis"}],
            "summary": {"persona_name": "Nathalie", "content": "Synthèse"},
        },
    )
    detail = storage.get_meeting(plugin_dir, meeting_id)
    assert detail is not None
    assert isinstance(detail["summary"], dict)
    assert detail["summary"]["content"] == "Synthèse"


@pytest.mark.asyncio
async def test_stream_ask_yields_before_slow_persona_finishes(
    plugin_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_order: list[str] = []

    async def tracked_run(
        *,
        settings: Any,
        provider_set: Any,
        system_prompt: str,
        user_prompt: str,
        locale: str,
    ) -> str:
        _ = (settings, provider_set, system_prompt, user_prompt, locale)
        if "RH" in system_prompt or "rh" in system_prompt.lower():
            call_order.append("start_rh")
            await asyncio.sleep(0.08)
            call_order.append("end_rh")
            return "RH lent"
        call_order.append("fast")
        return "Rapide"

    monkeypatch.setattr(orchestrator, "_run_persona_prompt", tracked_run)
    events: list[dict] = []
    async for event in orchestrator.stream_ask(
        plugin_data_dir=plugin_dir,
        persona_ids=["01", "03"],
        question="Question test",
        context="",
        settings=object(),
        provider_set=None,
        locale="fr",
        rag_store=None,
    ):
        if event.get("type") == "persona_opinion":
            events.append(event)

    assert len(events) == 2
    assert "fast" in call_order[0:2] or call_order[0] == "fast"


@pytest.mark.asyncio
async def test_generate_opinions_parallelizes_llm_calls(
    plugin_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    in_flight = {"current": 0, "max": 0}

    async def tracked_run(
        *,
        settings: Any,
        provider_set: Any,
        system_prompt: str,
        user_prompt: str,
        locale: str,
    ) -> str:
        _ = (settings, provider_set, system_prompt, user_prompt, locale)
        in_flight["current"] += 1
        in_flight["max"] = max(in_flight["max"], in_flight["current"])
        await asyncio.sleep(0.05)
        in_flight["current"] -= 1
        return "Intervention simulée."

    monkeypatch.setattr(orchestrator, "_run_persona_prompt", tracked_run)
    await orchestrator.generate_opinions(
        plugin_data_dir=plugin_dir,
        persona_ids=["01", "03"],
        question="Ce contrat est-il clair ?",
        context="Brouillon v2",
        settings=object(),
        provider_set=None,
        locale="fr",
        rag_store=None,
    )
    assert in_flight["max"] >= 2


@pytest.mark.asyncio
async def test_stream_ask_cancels_pending_personas_when_consumer_closes(
    plugin_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slow_started = asyncio.Event()
    slow_cancelled = asyncio.Event()

    async def tracked_run(
        *,
        settings: Any,
        provider_set: Any,
        system_prompt: str,
        user_prompt: str,
        locale: str,
    ) -> str:
        _ = (settings, provider_set, user_prompt, locale)
        if "rh" in system_prompt.lower():
            slow_started.set()
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                slow_cancelled.set()
                raise
        await slow_started.wait()
        return "Rapide"

    monkeypatch.setattr(orchestrator, "_run_persona_prompt", tracked_run)

    stream = orchestrator.stream_ask(
        plugin_data_dir=plugin_dir,
        persona_ids=["01", "03"],
        question="Question test",
        context="",
        settings=object(),
        provider_set=None,
        locale="fr",
        rag_store=None,
    )
    try:
        async for event in stream:
            if event.get("type") == "persona_opinion":
                break
    finally:
        await stream.aclose()

    await asyncio.wait_for(slow_started.wait(), timeout=0.2)
    await asyncio.wait_for(slow_cancelled.wait(), timeout=0.2)
