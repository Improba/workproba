"""Tests SpecialistRun mode Regard (P2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.models.test import TestModel

from app.agent.tools import ToolContext, ToolDeps, build_agent
from app.limits import DEFAULT_LIMITS
from app.plugins.ports.managed_regards import (
    create_personas_managed_port,
    dual_read_catalog_entries,
    sign_bundle_for_tests,
)
from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD, PLUGIN_WORKPROBA_PERSONAS
from app.plugins.workproba_cloud import storage as cloud_storage
from app.plugins.workproba_personas import orchestrator, specialist_run, storage as personas_storage
from app.plugins.workproba_personas.tool_allowlist import (
    active_connectors_snapshot,
    resolve_panel_tools,
    resolve_tool_filter,
    ResolvedReadTool,
)
from app.sandbox.runner import SandboxRunner

from conftest import FakeProjectClient

IHORA_TOOLS = [
    {
        "name": "list_absences",
        "action": "list_absences",
        "description": "Lister les absences",
        "effect": "read",
        "visibility": "guided",
        "input_schema": {
            "type": "object",
            "properties": {
                "from": {"type": "string"},
                "to": {"type": "string"},
                "email": {"type": "string"},
            },
            "required": ["from", "to"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_timesheet",
        "action": "get_timesheet",
        "description": "Recuperer le timesheet",
        "effect": "read",
        "visibility": "guided",
        "input_schema": {
            "type": "object",
            "properties": {
                "from": {"type": "string"},
                "to": {"type": "string"},
                "email": {"type": "string"},
            },
            "required": ["from", "to"],
            "additionalProperties": False,
        },
    },
    {
        "name": "create_timesheet",
        "action": "create_timesheet",
        "description": "Creer une saisie de temps",
        "effect": "write",
        "visibility": "standard",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string"},
                "hours": {"type": "number"},
            },
            "required": ["date", "hours"],
            "additionalProperties": False,
        },
    },
]


def _sample_specialist_with_tools() -> dict[str, object]:
    return {
        "id": "org.rh",
        "name": "Agent RH",
        "role": "RH",
        "system_prompt": "Tu es RH.",
        "is_business_agent": True,
        "tools": {
            "allowed": [
                {"connector_id": "ihora", "tool": "list_absences"},
                {"connector_id": "ihora", "tool": "get_timesheet"},
                {"connector_id": "ihora", "tool": "create_timesheet"},
            ],
            "forbidden": [],
        },
    }


def _seed_ihora_connectors_cache(cloud_dir: Path) -> None:
    cloud_storage.save_known_managed_connectors(
        cloud_dir,
        [{"id": "ihora", "name": "Ihora", "tools": IHORA_TOOLS}],
    )


def test_resolve_panel_maps_refs_to_managed_read_tools() -> None:
    specialist = _sample_specialist_with_tools()
    snapshot = [{"id": "ihora", "name": "Ihora", "tools": IHORA_TOOLS}]
    resolution = resolve_panel_tools(specialist, snapshot)

    assert len(resolution.allowed_read_tools) == 2
    managed_names = {tool.managed_name for tool in resolution.allowed_read_tools}
    assert managed_names == {
        "managed__ihora__list_absences",
        "managed__ihora__get_timesheet",
    }


def test_resolve_panel_excludes_write_tools_from_registration() -> None:
    specialist = _sample_specialist_with_tools()
    snapshot = [{"id": "ihora", "name": "Ihora", "tools": IHORA_TOOLS}]
    resolution = resolve_panel_tools(specialist, snapshot)

    write_degraded = [
        entry
        for entry in resolution.degraded_tools
        if entry.tool == "create_timesheet"
    ]
    assert len(write_degraded) == 1
    assert write_degraded[0].reason == "effect_not_read"
    assert "managed__ihora__create_timesheet" not in {
        tool.managed_name for tool in resolution.allowed_read_tools
    }


def test_regard_agent_does_not_register_write_or_generic_invoke(tmp_path: Path) -> None:
    from pydantic_ai import Agent
    from pydantic_ai.models.test import TestModel

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    _seed_ihora_connectors_cache(cloud_dir)

    specialist = _sample_specialist_with_tools()
    resolution = resolve_panel_tools(
        specialist,
        active_connectors_snapshot(cloud_dir),
    )
    agent: Agent[ToolDeps, str] = Agent(
        TestModel(),
        deps_type=ToolDeps,
        output_type=str,
    )
    specialist_run.register_regard_tools(
        agent,
        resolution.allowed_read_tools,
        ui_mode="agent",
    )
    names = set(agent._function_toolset.tools.keys())
    assert "managed__ihora__list_absences" in names
    assert "managed__ihora__get_timesheet" in names
    assert "managed__ihora__create_timesheet" not in names
    assert "invoke_managed_connector" not in names


@pytest.mark.asyncio
async def test_regard_read_invoke_skips_hag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.agent.confirmation import ConfirmationGate

    class FailGate(ConfirmationGate):
        async def request_effect(self, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("gate must not run for read tools in regard mode")

    captured: dict[str, Any] = {}

    async def fake_impl(ctx, *, connector_id, payload, gate_tool_name, **kwargs):
        captured["connector_id"] = connector_id
        captured["payload"] = payload
        captured["gate_tool_name"] = gate_tool_name
        return {"ok": True, "human_summary": "done"}

    monkeypatch.setattr(
        "app.plugins.workproba_personas.specialist_run.invoke_managed_connector_impl",
        fake_impl,
    )

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    plugins_root = cloud_dir.parent
    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.test"})
    _seed_ihora_connectors_cache(cloud_dir)

    specialist = _sample_specialist_with_tools()
    resolution = resolve_panel_tools(
        specialist,
        active_connectors_snapshot(cloud_dir),
    )
    agent: Agent[ToolDeps, str] = Agent(
        TestModel(),
        deps_type=ToolDeps,
        output_type=str,
    )
    specialist_run.register_regard_tools(
        agent,
        resolution.allowed_read_tools,
        ui_mode="agent",
    )
    deps = specialist_run.build_regard_tool_deps(
        plugins_root=plugins_root,
        locale="fr",
        cloud_plugin_data_dir=cloud_dir,
        confirmation_gate=FailGate(session_id="s1", turn_id="t1"),
        project_client=FakeProjectClient(),
    )
    tool = agent._function_toolset.tools["managed__ihora__list_absences"]
    ctx = RunContext(
        deps=deps,
        model=TestModel(),
        usage=None,
        prompt=None,
        tool_call_id="tc-regard-read",
    )

    await tool.function(ctx, **{"from": "2026-01-01", "to": "2026-01-31", "email": "a@b.c"})
    assert captured["gate_tool_name"] == "managed__ihora__list_absences"
    assert captured["payload"]["action"] == "list_absences"


def test_connector_off_populates_degraded_tools(tmp_path: Path) -> None:
    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    _seed_ihora_connectors_cache(cloud_dir)
    cloud_storage.set_managed_connector_enabled(cloud_dir, "ihora", enabled=False)

    specialist = _sample_specialist_with_tools()
    resolution = resolve_panel_tools(
        specialist,
        active_connectors_snapshot(cloud_dir),
    )

    assert resolution.allowed_read_tools == []
    assert len(resolution.degraded_tools) == 3
    assert all(entry.reason == "connector_unavailable" for entry in resolution.degraded_tools)


@pytest.mark.asyncio
async def test_legacy_personas_only_regression(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plugin_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_PERSONAS
    plugin_dir.mkdir(parents=True)

    async def fake_run(**kwargs: Any) -> str:
        return "Intervention simulée."

    monkeypatch.setattr(orchestrator, "_run_persona_prompt", fake_run)
    opinions, warnings, degraded_tools = await orchestrator.generate_opinions(
            plugin_data_dir=plugin_dir,
            persona_ids=["01"],
            question="Avis ?",
            context="",
            settings=object(),
            provider_set=None,
            locale="fr",
            rag_store=None,
    )
    assert len(opinions) == 1
    assert opinions[0]["persona_name"] == "RH"
    assert warnings == []
    assert degraded_tools == []
    assert "degraded_tools" not in opinions[0]


def test_dual_read_prefers_specialists_for_regard_resolution(tmp_path: Path) -> None:
    personas_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_PERSONAS
    personas_dir.mkdir(parents=True)
    port = create_personas_managed_port(personas_dir)
    bundle = sign_bundle_for_tests(
        catalog_id="dual-read",
        version="1.0.0",
        name="Dual read",
        personas=[
            {
                "id": "legacy-01",
                "name": "Legacy",
                "system_prompt": "Legacy.",
            }
        ],
        specialists=[_sample_specialist_with_tools()],
    )
    port.install_catalog_version(bundle)
    port.activate_catalog("dual-read")

    catalog = port.active_specialist_set()
    assert catalog is not None
    entries = dual_read_catalog_entries(
        {
            "personas": catalog["personas"],
            "specialists": catalog["specialists"],
        }
    )
    assert entries[0]["id"] == "org.rh"

    resolved = personas_storage.resolve_personas(personas_dir, ["org.rh"])
    assert len(resolved) == 1
    assert specialist_run.specialist_has_panel_tools(resolved[0]) is True


@pytest.mark.asyncio
async def test_run_regard_returns_degraded_tools_when_connector_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run(self, user_prompt, *, deps=None, **kwargs):  # type: ignore[no-untyped-def]
        _ = (self, user_prompt, deps, kwargs)
        return type("R", (), {"output": "Avis specialist."})()

    def fake_build_regard_agent(**kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        return type("A", (), {"run": fake_run})()

    monkeypatch.setattr(specialist_run, "build_specialist_agent", fake_build_regard_agent)

    personas_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_PERSONAS
    personas_dir.mkdir(parents=True)
    specialist = _sample_specialist_with_tools()

    content, degraded = await specialist_run.run_regard(
        specialist=specialist,
        question="Qui est absent ?",
        context="",
        settings=object(),
        provider_set=None,
        locale="fr",
        cloud_plugin_data_dir=None,
        plugins_root=personas_dir.parent,
    )
    assert content == "Avis specialist."
    assert len(degraded) == 3
    assert degraded[0]["reason"] == "connector_unavailable"


def test_resolve_panel_excludes_forbidden_tools() -> None:
    specialist = _sample_specialist_with_tools()
    specialist["tools"]["forbidden"] = [{"connector_id": "ihora", "tool": "list_absences"}]
    snapshot = [{"id": "ihora", "name": "Ihora", "tools": IHORA_TOOLS}]
    resolution = resolve_panel_tools(specialist, snapshot)

    managed_names = {tool.managed_name for tool in resolution.allowed_read_tools}
    assert "managed__ihora__list_absences" not in managed_names
    assert "managed__ihora__get_timesheet" in managed_names


def test_resolve_panel_operative_includes_write_tools() -> None:
    specialist = _sample_specialist_with_tools()
    snapshot = [{"id": "ihora", "name": "Ihora", "tools": IHORA_TOOLS}]
    resolution = resolve_panel_tools(specialist, snapshot, mode="operative")

    managed_names = {tool.managed_name for tool in resolution.allowed_panel_tools}
    assert managed_names == {
        "managed__ihora__list_absences",
        "managed__ihora__get_timesheet",
        "managed__ihora__create_timesheet",
    }


@pytest.mark.asyncio
async def test_read_shim_action_override_ignored(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_impl(ctx, *, connector_id, payload, gate_tool_name, **kwargs):
        captured["payload"] = payload
        return {"ok": True}

    monkeypatch.setattr(
        "app.plugins.workproba_personas.specialist_run.invoke_managed_connector_impl",
        fake_impl,
    )

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    _seed_ihora_connectors_cache(cloud_dir)
    specialist = _sample_specialist_with_tools()
    resolution = resolve_panel_tools(
        specialist,
        active_connectors_snapshot(cloud_dir),
    )
    tool_def = resolution.allowed_read_tools[0].tool_def
    shim = specialist_run._make_read_tool_shim(
        "ihora",
        tool_def,
        managed_name="managed__ihora__list_absences",
    )
    deps = specialist_run.build_regard_tool_deps(
        plugins_root=cloud_dir.parent,
        locale="fr",
        cloud_plugin_data_dir=cloud_dir,
        project_client=FakeProjectClient(),
    )
    ctx = RunContext(
        deps=deps,
        model=TestModel(),
        usage=None,
        prompt=None,
        tool_call_id="tc-action-override",
    )
    await shim(ctx, action="create_timesheet", **{"from": "2026-01-01", "to": "2026-01-31"})
    assert captured["payload"]["action"] == "list_absences"


@pytest.mark.asyncio
async def test_read_shim_rejects_non_read_effect(tmp_path: Path) -> None:
    write_tool_def = next(tool for tool in IHORA_TOOLS if tool["effect"] == "write")
    shim = specialist_run._make_read_tool_shim(
        "ihora",
        write_tool_def,
        managed_name="managed__ihora__create_timesheet",
    )
    deps = specialist_run.build_regard_tool_deps(
        plugins_root=tmp_path,
        locale="fr",
        project_client=FakeProjectClient(),
    )
    ctx = RunContext(
        deps=deps,
        model=TestModel(),
        usage=None,
        prompt=None,
        tool_call_id="tc-effect-block",
    )
    result = await shim(ctx, date="2026-01-01", hours=8)
    assert result["ok"] is False
    assert result["error"] == "effect_not_read"


def test_register_regard_tools_skips_non_read_effect(tmp_path: Path) -> None:
    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    _seed_ihora_connectors_cache(cloud_dir)
    specialist = _sample_specialist_with_tools()
    resolution = resolve_panel_tools(
        specialist,
        active_connectors_snapshot(cloud_dir),
        mode="operative",
    )
    agent: Agent[ToolDeps, str] = Agent(
        TestModel(),
        deps_type=ToolDeps,
        output_type=str,
    )
    specialist_run.register_regard_tools(
        agent,
        [
            ResolvedReadTool(
                connector_id="ihora",
                tool_name="create_timesheet",
                managed_name="managed__ihora__create_timesheet",
                tool_def=next(tool for tool in IHORA_TOOLS if tool["effect"] == "write"),
            )
        ],
        ui_mode="agent",
    )
    names = set(agent._function_toolset.tools.keys())
    assert names == set()
    assert len(resolution.allowed_panel_tools) == 3


def test_build_specialist_system_prompt_includes_panel_notice() -> None:
    specialist = _sample_specialist_with_tools()
    resolution = resolve_panel_tools(
        specialist,
        [{"id": "ihora", "name": "Ihora", "tools": IHORA_TOOLS}],
    )
    prompt = specialist_run.build_specialist_system_prompt(
        specialist,
        locale="fr",
        resolution=resolution,
        mode="regard",
    )
    assert "managed__ihora__list_absences" in prompt
    assert "create_timesheet" in prompt


def _register_tools_for_filter(
    tmp_path: Path,
    specialist: dict[str, object],
    *,
    mode: str,
) -> Agent[ToolDeps, str]:
    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    _seed_ihora_connectors_cache(cloud_dir)
    resolution = resolve_panel_tools(
        specialist,
        active_connectors_snapshot(cloud_dir),
        mode=mode,  # type: ignore[arg-type]
    )
    tool_filter = resolve_tool_filter(specialist, mode)  # type: ignore[arg-type]
    agent: Agent[ToolDeps, str] = Agent(
        TestModel(),
        deps_type=ToolDeps,
        output_type=str,
    )
    if tool_filter != "disabled":
        if mode == "regard" or tool_filter == "pure_read":
            specialist_run.register_regard_tools(
                agent,
                resolution.allowed_read_tools,
                ui_mode="agent",
            )
        else:
            specialist_run.register_operative_tools(
                agent,
                resolution.allowed_panel_tools,
                ui_mode="agent",
            )
    return agent


def test_tool_filter_disabled_registers_no_tools(tmp_path: Path) -> None:
    specialist = _sample_specialist_with_tools()
    specialist["modes"] = {"regard": {"tool_filter": "disabled"}}
    agent = _register_tools_for_filter(tmp_path, specialist, mode="regard")
    assert agent._function_toolset.tools == {}


def test_tool_filter_pure_read_operative_skips_write(tmp_path: Path) -> None:
    specialist = _sample_specialist_with_tools()
    specialist["modes"] = {"operative": {"tool_filter": "pure_read"}}
    agent = _register_tools_for_filter(tmp_path, specialist, mode="operative")
    names = set(agent._function_toolset.tools.keys())
    assert "managed__ihora__list_absences" in names
    assert "managed__ihora__create_timesheet" not in names


def test_tool_filter_defaults_match_cloud_contract() -> None:
    specialist = _sample_specialist_with_tools()
    assert resolve_tool_filter(specialist, "regard") == "pure_read"
    assert resolve_tool_filter(specialist, "operative") == "allowlist"


def test_operative_agent_registers_write_tools(tmp_path: Path) -> None:
    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    _seed_ihora_connectors_cache(cloud_dir)
    specialist = _sample_specialist_with_tools()
    resolution = resolve_panel_tools(
        specialist,
        active_connectors_snapshot(cloud_dir),
        mode="operative",
    )
    agent: Agent[ToolDeps, str] = Agent(
        TestModel(),
        deps_type=ToolDeps,
        output_type=str,
    )
    specialist_run.register_operative_tools(
        agent,
        resolution.allowed_panel_tools,
        ui_mode="agent",
    )
    names = set(agent._function_toolset.tools.keys())
    assert "managed__ihora__create_timesheet" in names
    assert "managed__ihora__list_absences" in names


@pytest.mark.asyncio
async def test_operative_write_calls_confirmation_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.agent.confirmation import ConfirmationGate
    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient

    gate_calls: list[str] = []

    class CaptureGate(ConfirmationGate):
        async def notify_preparing(self, **kwargs):  # type: ignore[no-untyped-def]
            gate_calls.append("notify_preparing")

        async def request_effect(self, **kwargs):  # type: ignore[no-untyped-def]
            gate_calls.append("request_effect")
            return "approved"

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    plugins_root = cloud_dir.parent
    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.test"})
    cloud_storage.set_managed_connector_enabled(cloud_dir, "ihora", enabled=True)
    _seed_ihora_connectors_cache(cloud_dir)
    client = CloudControlPlaneClient(
        base_url="https://cloud.test",
        plugin_data_dir=cloud_dir,
    )
    client.save_tokens({"access_token": "tok", "org_id": "org-a", "device_id": "dev-1"})

    async def fake_allowed(self: CloudControlPlaneClient) -> set[str]:
        return {"ihora"}

    async def fake_invoke_remote(self, connector_id, payload, identity):  # type: ignore[no-untyped-def]
        return {"ok": True, "result": {"action": "create_timesheet"}}

    monkeypatch.setattr(CloudControlPlaneClient, "fetch_allowed_connector_ids", fake_allowed)
    monkeypatch.setattr(
        "app.plugins.workproba_cloud.plugin.open_remote_capability_gateway",
        lambda **kwargs: type("GW", (), {"invoke_remote": fake_invoke_remote})(),
    )

    specialist = _sample_specialist_with_tools()
    resolution = resolve_panel_tools(
        specialist,
        active_connectors_snapshot(cloud_dir),
        mode="operative",
    )
    agent: Agent[ToolDeps, str] = Agent(
        TestModel(),
        deps_type=ToolDeps,
        output_type=str,
    )
    specialist_run.register_operative_tools(
        agent,
        resolution.allowed_panel_tools,
        ui_mode="agent",
    )
    deps = specialist_run.build_regard_tool_deps(
        plugins_root=plugins_root,
        locale="fr",
        cloud_plugin_data_dir=cloud_dir,
        confirmation_gate=CaptureGate(session_id="s1", turn_id="t1"),
        project_client=FakeProjectClient(),
    )
    tool = agent._function_toolset.tools["managed__ihora__create_timesheet"]
    ctx = RunContext(
        deps=deps,
        model=TestModel(),
        usage=None,
        prompt=None,
        tool_call_id="tc-operative-write",
    )
    result = await tool.function(ctx, date="2026-01-01", hours=8)
    assert result["ok"] is True
    assert "request_effect" in gate_calls


@pytest.mark.asyncio
async def test_operative_write_denied_by_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic_ai.exceptions import ModelRetry

    from app.agent.confirmation import ConfirmationGate
    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient

    class DenyGate(ConfirmationGate):
        async def request_effect(self, **kwargs):  # type: ignore[no-untyped-def]
            return "denied"

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    plugins_root = cloud_dir.parent
    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.test"})
    cloud_storage.set_managed_connector_enabled(cloud_dir, "ihora", enabled=True)
    _seed_ihora_connectors_cache(cloud_dir)
    client = CloudControlPlaneClient(
        base_url="https://cloud.test",
        plugin_data_dir=cloud_dir,
    )
    client.save_tokens({"access_token": "tok", "org_id": "org-a", "device_id": "dev-1"})

    async def fake_allowed(self: CloudControlPlaneClient) -> set[str]:
        return {"ihora"}

    monkeypatch.setattr(CloudControlPlaneClient, "fetch_allowed_connector_ids", fake_allowed)

    specialist = _sample_specialist_with_tools()
    resolution = resolve_panel_tools(
        specialist,
        active_connectors_snapshot(cloud_dir),
        mode="operative",
    )
    agent: Agent[ToolDeps, str] = Agent(
        TestModel(),
        deps_type=ToolDeps,
        output_type=str,
    )
    specialist_run.register_operative_tools(
        agent,
        resolution.allowed_panel_tools,
        ui_mode="agent",
    )
    deps = specialist_run.build_regard_tool_deps(
        plugins_root=plugins_root,
        locale="fr",
        cloud_plugin_data_dir=cloud_dir,
        confirmation_gate=DenyGate(session_id="s1", turn_id="t1"),
        project_client=FakeProjectClient(),
    )
    tool = agent._function_toolset.tools["managed__ihora__create_timesheet"]
    ctx = RunContext(
        deps=deps,
        model=TestModel(),
        usage=None,
        prompt=None,
        tool_call_id="tc-operative-deny",
    )
    with pytest.raises(ModelRetry):
        await tool.function(ctx, date="2026-01-01", hours=8)


@pytest.mark.asyncio
async def test_operative_toctou_connector_disabled_after_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic_ai.exceptions import ModelRetry

    from app.agent.confirmation import ConfirmationGate
    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient

    class ApproveGate(ConfirmationGate):
        async def request_effect(self, **kwargs):  # type: ignore[no-untyped-def]
            cloud_storage.set_managed_connector_enabled(cloud_dir, "ihora", enabled=False)
            return "approved"

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    plugins_root = cloud_dir.parent
    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.test"})
    cloud_storage.set_managed_connector_enabled(cloud_dir, "ihora", enabled=True)
    _seed_ihora_connectors_cache(cloud_dir)
    client = CloudControlPlaneClient(
        base_url="https://cloud.test",
        plugin_data_dir=cloud_dir,
    )
    client.save_tokens({"access_token": "tok", "org_id": "org-a", "device_id": "dev-1"})

    async def fake_allowed(self: CloudControlPlaneClient) -> set[str]:
        return {"ihora"}

    monkeypatch.setattr(CloudControlPlaneClient, "fetch_allowed_connector_ids", fake_allowed)

    specialist = _sample_specialist_with_tools()
    resolution = resolve_panel_tools(
        specialist,
        active_connectors_snapshot(cloud_dir),
        mode="operative",
    )
    agent: Agent[ToolDeps, str] = Agent(
        TestModel(),
        deps_type=ToolDeps,
        output_type=str,
    )
    specialist_run.register_operative_tools(
        agent,
        resolution.allowed_panel_tools,
        ui_mode="agent",
    )
    deps = specialist_run.build_regard_tool_deps(
        plugins_root=plugins_root,
        locale="fr",
        cloud_plugin_data_dir=cloud_dir,
        confirmation_gate=ApproveGate(session_id="s1", turn_id="t1"),
        project_client=FakeProjectClient(),
    )
    tool = agent._function_toolset.tools["managed__ihora__create_timesheet"]
    ctx = RunContext(
        deps=deps,
        model=TestModel(),
        usage=None,
        prompt=None,
        tool_call_id="tc-operative-toctou",
    )
    with pytest.raises(ModelRetry, match="désactivé"):
        await tool.function(ctx, date="2026-01-01", hours=8)


@pytest.mark.asyncio
async def test_operative_write_without_gate_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic_ai.exceptions import ModelRetry

    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    plugins_root = cloud_dir.parent
    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.test"})
    cloud_storage.set_managed_connector_enabled(cloud_dir, "ihora", enabled=True)
    _seed_ihora_connectors_cache(cloud_dir)
    client = CloudControlPlaneClient(
        base_url="https://cloud.test",
        plugin_data_dir=cloud_dir,
    )
    client.save_tokens({"access_token": "tok", "org_id": "org-a", "device_id": "dev-1"})

    async def fake_allowed(self: CloudControlPlaneClient) -> set[str]:
        return {"ihora"}

    monkeypatch.setattr(CloudControlPlaneClient, "fetch_allowed_connector_ids", fake_allowed)

    specialist = _sample_specialist_with_tools()
    resolution = resolve_panel_tools(
        specialist,
        active_connectors_snapshot(cloud_dir),
        mode="operative",
    )
    agent: Agent[ToolDeps, str] = Agent(
        TestModel(),
        deps_type=ToolDeps,
        output_type=str,
    )
    specialist_run.register_operative_tools(
        agent,
        resolution.allowed_panel_tools,
        ui_mode="agent",
    )
    deps = specialist_run.build_regard_tool_deps(
        plugins_root=plugins_root,
        locale="fr",
        cloud_plugin_data_dir=cloud_dir,
        confirmation_gate=None,
        project_client=FakeProjectClient(),
    )
    tool = agent._function_toolset.tools["managed__ihora__create_timesheet"]
    ctx = RunContext(
        deps=deps,
        model=TestModel(),
        usage=None,
        prompt=None,
        tool_call_id="tc-operative-no-gate",
    )
    with pytest.raises(ModelRetry, match="confirmation humaine"):
        await tool.function(ctx, date="2026-01-01", hours=8)


@pytest.mark.asyncio
async def test_regard_toctou_effect_change_requires_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic_ai.exceptions import ModelRetry

    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient

    cloud_dir = tmp_path / "plugins" / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir(parents=True)
    plugins_root = cloud_dir.parent
    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.test"})
    cloud_storage.set_managed_connector_enabled(cloud_dir, "ihora", enabled=True)
    _seed_ihora_connectors_cache(cloud_dir)
    client = CloudControlPlaneClient(
        base_url="https://cloud.test",
        plugin_data_dir=cloud_dir,
    )
    client.save_tokens({"access_token": "tok", "org_id": "org-a", "device_id": "dev-1"})

    async def fake_allowed(self: CloudControlPlaneClient) -> set[str]:
        return {"ihora"}

    monkeypatch.setattr(CloudControlPlaneClient, "fetch_allowed_connector_ids", fake_allowed)

    specialist = _sample_specialist_with_tools()
    resolution = resolve_panel_tools(
        specialist,
        active_connectors_snapshot(cloud_dir),
    )
    read_tool = next(
        tool for tool in resolution.allowed_read_tools if tool.tool_name == "list_absences"
    )
    agent: Agent[ToolDeps, str] = Agent(
        TestModel(),
        deps_type=ToolDeps,
        output_type=str,
    )
    specialist_run.register_regard_tools(
        agent,
        resolution.allowed_read_tools,
        ui_mode="agent",
    )

    mutated_tools = [
        {
            **tool,
            "effect": "write" if tool.get("action") == "list_absences" else tool.get("effect"),
        }
        for tool in IHORA_TOOLS
    ]
    cloud_storage.save_known_managed_connectors(
        cloud_dir,
        [{"id": "ihora", "name": "Ihora", "tools": mutated_tools}],
    )

    deps = specialist_run.build_regard_tool_deps(
        plugins_root=plugins_root,
        locale="fr",
        cloud_plugin_data_dir=cloud_dir,
        confirmation_gate=None,
        project_client=FakeProjectClient(),
    )
    tool = agent._function_toolset.tools[read_tool.managed_name]
    ctx = RunContext(
        deps=deps,
        model=TestModel(),
        usage=None,
        prompt=None,
        tool_call_id="tc-regard-toctou-effect",
    )
    with pytest.raises(ModelRetry, match="confirmation humaine"):
        await tool.function(
            ctx,
            **{"from": "2026-01-01", "to": "2026-01-31", "email": "a@b.c"},
        )
