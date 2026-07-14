"""Tests Human Approval Gate orienté effet (B2a voie B)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel

from app.agent.confirmation import ConfirmationGate
from app.agent.effects import (
    EffectProtection,
    EffectProposal,
    classify_effect,
    effect_headline,
    effect_label,
    protection_labels,
)
from app.agent.tools import ToolContext, ToolDeps, build_agent
from app.audit import read_audit
from app.limits import DEFAULT_LIMITS
from app.plugins.workproba_projet import PLUGIN_ID
from app.plugins.workproba_projet import storage
from app.sandbox.runner import SandboxRunner
from app.schemas import ConfirmationRequestEvent

from conftest import FakeProjectClient


class RecordingGate(ConfirmationGate):
    """Gate qui enregistre les appels request_effect et approuve par défaut."""

    def __init__(self, *, session_id: str = "s1", turn_id: str = "t1") -> None:
        super().__init__(session_id=session_id, turn_id=turn_id)
        self.effect_calls: list[EffectProposal] = []
        self.auto_approve = True

    async def request_effect(
        self,
        *,
        tool_call_id: str,
        proposal: EffectProposal,
        audit_app_data_dir: Path | None = None,
        audit_enabled: bool | None = None,
    ) -> bool:
        self.effect_calls.append(proposal)
        if not self.auto_approve:
            return False
        return True


def _deps(
    *,
    project_root: Path,
    gate: ConfirmationGate | None = None,
    workspace_data_dir: Path | None = None,
    plugin_data_dir: Path | None = None,
) -> ToolDeps:
    return ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s1",
            documents=[],
            project_root=project_root,
            workspace_data_dir=workspace_data_dir,
            plugin_data_dir=plugin_data_dir,
            locale="fr",
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
        confirmation_gate=gate,
    )


def _ctx(deps: ToolDeps, tool_call_id: str = "tc1") -> RunContext[ToolDeps]:
    return RunContext(
        deps=deps,
        model=TestModel(),
        usage=None,
        prompt=None,
        tool_call_id=tool_call_id,
    )


@pytest.mark.parametrize(
    ("tool_name", "args", "expected_effect"),
    [
        ("write_docx", {"path": "a.docx"}, "create"),
        ("write_xlsx", {"path": "a.xlsx"}, "create"),
        ("write_pdf", {"path": "a.pdf"}, "create"),
        ("generate_document", {"name": "note.md"}, "create"),
        (
            "publish_artifact",
            {"name": "doc.pdf", "project": "Alpha", "project_id": "p1"},
            "publish",
        ),
        ("sync_to_cloud", {"project_id": "p1"}, "external_send"),
        ("web_search", {"query": "pytest"}, "network_access"),
        ("browser_navigate", {"url": "https://example.com"}, "network_access"),
        ("run_code", {"code": "print(1)"}, "code_execute"),
        ("read_document", {"document_id": "a"}, None),
        ("list_files", {}, None),
        ("unknown_future_tool", {}, None),
    ],
)
def test_classify_effect_mapping(
    tool_name: str,
    args: dict[str, Any],
    expected_effect: str | None,
) -> None:
    proposal = classify_effect(tool_name, args, permissions_network=True)
    if expected_effect is None:
        assert proposal is None
        return
    assert proposal is not None
    assert proposal.effect == expected_effect
    assert proposal.tool_name == tool_name


def test_classify_effect_write_docx_modify(tmp_path: Path) -> None:
    existing = tmp_path / "report.docx"
    existing.write_bytes(b"PK")
    proposal = classify_effect(
        "write_docx",
        {"path": "report.docx", "project_root": tmp_path},
        permissions_network=True,
    )
    assert proposal is not None
    assert proposal.action == "modify"
    assert proposal.effect == "modify"
    assert proposal.protections.version_before_modify is True
    assert proposal.protections.preview is True


def test_classify_effect_write_docx_create(tmp_path: Path) -> None:
    proposal = classify_effect(
        "write_docx",
        {"path": "new.docx", "project_root": tmp_path},
        permissions_network=True,
    )
    assert proposal is not None
    assert proposal.action == "create"
    assert proposal.effect == "create"
    assert proposal.protections.version_before_modify is False


def test_effect_label_fr_en() -> None:
    assert effect_label("create", "fr") == "Créer"
    assert effect_label("network_access", "en") == "Network access"


@pytest.mark.parametrize(
    ("effect", "targets", "locale", "expected"),
    [
        ("create", ["Note.docx"], "fr", "Je vais Créer : Note.docx"),
        ("modify", ["Rapport.xlsx"], "fr", "Je vais Modifier : Rapport.xlsx"),
        ("publish", ["doc.pdf", "Alpha"], "fr", "Je vais publier : doc.pdf dans Alpha"),
        ("network_access", ["pytest"], "fr", "Je vais accéder au réseau : pytest"),
        ("code_execute", [], "fr", "Je vais exécuter du code"),
        ("external_send", ["p1"], "fr", "Je vais envoyer à l'extérieur : p1"),
        ("create", ["Note.docx"], "en", "I will Create: Note.docx"),
        ("modify", ["Report.xlsx"], "en", "I will Modify: Report.xlsx"),
        ("publish", ["doc.pdf", "Alpha"], "en", "I will publish: doc.pdf in Alpha"),
        ("network_access", ["pytest"], "en", "I will access the network: pytest"),
        ("code_execute", [], "en", "I will execute code"),
        ("external_send", ["p1"], "en", "I will send externally: p1"),
    ],
)
def test_effect_headline(
    effect: str,
    targets: list[str],
    locale: str,
    expected: str,
) -> None:
    proposal = EffectProposal(
        effect=effect,  # type: ignore[arg-type]
        tool_name="test",
        targets=targets,
    )
    assert effect_headline(proposal, locale) == expected


def test_protection_labels_create() -> None:
    proposal = EffectProposal(
        effect="create",
        tool_name="write_docx",
        protections=EffectProtection(
            preview=True,
            version_before_modify=False,
            network_used=False,
            external_send=False,
        ),
    )
    labels = protection_labels(proposal, "fr")
    assert labels == [
        "Aperçu disponible avant création",
        "Aucun accès réseau",
        "Aucun envoi externe",
    ]


def test_protection_labels_modify() -> None:
    proposal = EffectProposal(
        effect="modify",
        tool_name="write_docx",
        protections=EffectProtection(
            preview=True,
            version_before_modify=True,
            network_used=False,
            external_send=False,
        ),
    )
    labels = protection_labels(proposal, "fr")
    assert "Version automatique avant modification" in labels
    assert "Aperçu disponible avant création" in labels


def test_protection_labels_network_access_skips_no_network() -> None:
    proposal = EffectProposal(
        effect="network_access",
        tool_name="web_search",
        protections=EffectProtection(
            preview=False,
            version_before_modify=False,
            network_used=True,
            external_send=False,
        ),
    )
    labels = protection_labels(proposal, "en")
    assert "No network access" not in labels
    assert "No external send" in labels


@pytest.mark.asyncio
async def test_concurrent_request_effect_serialized() -> None:
    gate = ConfirmationGate(session_id="s1", turn_id="t-serialize")
    proposal_a = EffectProposal(
        effect="create",
        tool_name="write_docx",
        targets=["a.docx"],
        action="create",
        proposed_path="a.docx",
        human_summary="Créer a.docx",
    )
    proposal_b = EffectProposal(
        effect="create",
        tool_name="write_docx",
        targets=["b.docx"],
        action="create",
        proposed_path="b.docx",
        human_summary="Créer b.docx",
    )

    pending_confirmations = 0
    max_pending = 0
    emission_order: list[str] = []

    async def consume_and_approve() -> None:
        nonlocal pending_confirmations, max_pending
        approved = 0
        while approved < 2:
            event = await gate.event_queue.get()
            if not isinstance(event, ConfirmationRequestEvent):
                continue
            pending_confirmations += 1
            max_pending = max(max_pending, pending_confirmations)
            emission_order.append(event.tool_call_id)
            await asyncio.sleep(0.05)
            gate.resolve(event.confirmation_id, "approve")
            pending_confirmations -= 1
            approved += 1

    consumer = asyncio.create_task(consume_and_approve())
    await asyncio.gather(
        gate.request_effect(tool_call_id="tc-a", proposal=proposal_a),
        gate.request_effect(tool_call_id="tc-b", proposal=proposal_b),
    )
    await consumer

    assert emission_order == ["tc-a", "tc-b"]
    assert max_pending == 1


@pytest.mark.asyncio
async def test_request_effect_emits_enriched_event() -> None:
    gate = ConfirmationGate(session_id="s1", turn_id="turn-42")
    proposal = EffectProposal(
        effect="create",
        tool_name="write_docx",
        targets=["out.docx"],
        action="create",
        human_summary="Créer out.docx",
        proposed_path="out.docx",
        headline="Je vais Créer : out.docx",
        protection_labels=[
            "Aperçu disponible avant création",
            "Aucun accès réseau",
            "Aucun envoi externe",
        ],
    )

    async def approve_later() -> None:
        await asyncio.sleep(0.05)
        event = gate.event_queue.get_nowait()
        assert isinstance(event, ConfirmationRequestEvent)
        assert event.effect == "create"
        assert event.targets == ["out.docx"]
        assert event.protections.get("preview") is False
        assert event.headline == "Je vais Créer : out.docx"
        assert event.protection_labels == [
            "Aperçu disponible avant création",
            "Aucun accès réseau",
            "Aucun envoi externe",
        ]
        gate.resolve(event.confirmation_id, "approve")

    asyncio.create_task(approve_later())
    approved = await gate.request_effect(tool_call_id="tc1", proposal=proposal)
    assert approved is True


@pytest.mark.asyncio
async def test_request_effect_deny_returns_false() -> None:
    gate = ConfirmationGate(session_id="s1", turn_id="t1")
    proposal = EffectProposal(
        effect="publish",
        tool_name="publish_artifact",
        targets=["doc.pdf", "Alpha"],
        action="create",
        proposed_path="artefacts/p1/doc.pdf",
        human_summary="Publier",
    )

    async def deny_later() -> None:
        await asyncio.sleep(0.05)
        event = gate.event_queue.get_nowait()
        assert isinstance(event, ConfirmationRequestEvent)
        gate.resolve(event.confirmation_id, "deny")

    asyncio.create_task(deny_later())
    approved = await gate.request_effect(tool_call_id="tc1", proposal=proposal)
    assert approved is False


@pytest.mark.asyncio
async def test_request_write_legacy_defaults() -> None:
    gate = ConfirmationGate(session_id="s1", turn_id="t1")

    async def approve_later() -> None:
        await asyncio.sleep(0.05)
        event = gate.event_queue.get_nowait()
        assert isinstance(event, ConfirmationRequestEvent)
        assert event.effect is None
        assert event.targets == []
        assert event.protections == {}
        gate.resolve(event.confirmation_id, "approve")

    asyncio.create_task(approve_later())
    approved = await gate.request_write(
        tool_call_id="tc1",
        tool_name="generate_document",
        action="create",
        proposed_path="note.md",
        human_summary="Créer note.md",
    )
    assert approved is True


def test_audit_on_request_effect(tmp_path: Path) -> None:
    app_data = tmp_path / "app_data"
    app_data.mkdir()

    async def run() -> None:
        gate = ConfirmationGate(session_id="s1", turn_id="turn-audit")
        proposal = EffectProposal(
            effect="create",
            tool_name="generate_document",
            targets=["note.md"],
            action="create",
            proposed_path="note.md",
            human_summary="Créer note.md",
        )

        async def approve_later() -> None:
            await asyncio.sleep(0.05)
            event = gate.event_queue.get_nowait()
            assert isinstance(event, ConfirmationRequestEvent)
            gate.resolve(event.confirmation_id, "approve")

        asyncio.create_task(approve_later())
        await gate.request_effect(
            tool_call_id="tc1",
            proposal=proposal,
            audit_app_data_dir=app_data,
        )

    asyncio.run(run())

    entries, _ = read_audit(app_data)
    events = [entry["event"] for entry in entries]
    assert "approval.requested" in events
    assert "approval.resolved" in events
    requested = next(e for e in entries if e["event"] == "approval.requested")
    resolved = next(e for e in entries if e["event"] == "approval.resolved")
    assert requested["details"]["work_id"] == "turn-audit"
    assert requested["details"]["effect"] == "create"
    assert resolved["details"]["decision"] == "approve"


def test_audit_disabled_on_request_effect(tmp_path: Path) -> None:
    app_data = tmp_path / "app_data"
    app_data.mkdir()

    async def run() -> None:
        gate = ConfirmationGate(session_id="s1", turn_id="turn-no-audit")
        proposal = EffectProposal(
            effect="create",
            tool_name="generate_document",
            targets=["note.md"],
            action="create",
            proposed_path="note.md",
            human_summary="Créer note.md",
        )

        async def approve_later() -> None:
            await asyncio.sleep(0.05)
            event = gate.event_queue.get_nowait()
            assert isinstance(event, ConfirmationRequestEvent)
            gate.resolve(event.confirmation_id, "approve")

        asyncio.create_task(approve_later())
        await gate.request_effect(
            tool_call_id="tc1",
            proposal=proposal,
            audit_app_data_dir=app_data,
            audit_enabled=False,
        )

    asyncio.run(run())

    entries, _ = read_audit(app_data)
    assert entries == []


@pytest.mark.asyncio
async def test_request_effect_timeout_writes_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_data = tmp_path / "app_data"
    app_data.mkdir()
    monkeypatch.setattr(
        "app.agent.confirmation.CONFIRMATION_TIMEOUT_SECONDS",
        0.05,
    )

    gate = ConfirmationGate(session_id="s1", turn_id="turn-timeout")
    proposal = EffectProposal(
        effect="create",
        tool_name="write_docx",
        targets=["out.docx"],
        action="create",
        proposed_path="out.docx",
        human_summary="Créer out.docx",
    )

    approved = await gate.request_effect(
        tool_call_id="tc1",
        proposal=proposal,
        audit_app_data_dir=app_data,
        audit_enabled=True,
    )
    assert approved is False

    entries, _ = read_audit(app_data)
    events = [entry["event"] for entry in entries]
    assert events == ["approval.requested", "approval.resolved"]
    resolved = next(e for e in entries if e["event"] == "approval.resolved")
    assert resolved["details"]["decision"] == "timeout"


def test_request_effect_deny_writes_audit(tmp_path: Path) -> None:
    app_data = tmp_path / "app_data"
    app_data.mkdir()

    async def run() -> None:
        gate = ConfirmationGate(session_id="s1", turn_id="turn-deny")
        proposal = EffectProposal(
            effect="publish",
            tool_name="publish_artifact",
            targets=["doc.pdf", "Alpha"],
            action="create",
            proposed_path="artefacts/p1/doc.pdf",
            human_summary="Publier",
        )

        async def deny_later() -> None:
            await asyncio.sleep(0.05)
            event = gate.event_queue.get_nowait()
            assert isinstance(event, ConfirmationRequestEvent)
            gate.resolve(event.confirmation_id, "deny")

        asyncio.create_task(deny_later())
        approved = await gate.request_effect(
            tool_call_id="tc1",
            proposal=proposal,
            audit_app_data_dir=app_data,
            audit_enabled=True,
        )
        assert approved is False

    asyncio.run(run())

    entries, _ = read_audit(app_data)
    resolved = next(e for e in entries if e["event"] == "approval.resolved")
    assert resolved["details"]["decision"] == "deny"


def test_multi_file_same_work_id_audit(tmp_path: Path) -> None:
    app_data = tmp_path / "app_data"
    app_data.mkdir()
    turn_id = "turn-multi"

    async def run() -> None:
        gate = ConfirmationGate(session_id="s1", turn_id=turn_id)

        async def approve_both() -> None:
            for _ in range(2):
                await asyncio.sleep(0.05)
                event = gate.event_queue.get_nowait()
                assert isinstance(event, ConfirmationRequestEvent)
                gate.resolve(event.confirmation_id, "approve")

        asyncio.create_task(approve_both())

        for name in ("a.docx", "b.docx"):
            proposal = EffectProposal(
                effect="create",
                tool_name="write_docx",
                targets=[name],
                action="create",
                proposed_path=name,
                human_summary=f"Créer {name}",
            )
            approved = await gate.request_effect(
                tool_call_id=f"tc-{name}",
                proposal=proposal,
                audit_app_data_dir=app_data,
                audit_enabled=True,
            )
            assert approved is True

    asyncio.run(run())

    entries, _ = read_audit(app_data)
    requested = [e for e in entries if e["event"] == "approval.requested"]
    resolved = [e for e in entries if e["event"] == "approval.resolved"]
    assert len(requested) == 2
    assert len(resolved) == 2
    assert all(e["details"]["work_id"] == turn_id for e in requested + resolved)


def test_classify_effect_search_kb_returns_none() -> None:
    proposal = classify_effect("search_kb", {"query": "pytest"}, permissions_network=True)
    assert proposal is None


@pytest.mark.asyncio
async def test_search_kb_does_not_call_request_effect(tmp_path: Path) -> None:
    gate = RecordingGate()
    client = FakeProjectClient()
    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s1",
            documents=[],
            project_root=tmp_path,
            locale="fr",
        ),
        project_client=client,
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
        confirmation_gate=gate,
    )
    agent = build_agent(TestModel())
    tool = agent._function_toolset.tools["search_kb"]
    ctx = _ctx(deps)

    await tool.function(ctx, query="hello")
    assert gate.effect_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name", ["write_docx", "write_xlsx", "write_pdf", "generate_document"])
async def test_write_tools_call_request_effect(
    tmp_path: Path,
    tool_name: str,
) -> None:
    gate = RecordingGate()
    deps = _deps(project_root=tmp_path, gate=gate)
    agent = build_agent(TestModel())
    tool = agent._function_toolset.tools[tool_name]
    ctx = _ctx(deps)

    if tool_name == "write_docx":
        await tool.function(ctx, path="out.docx", title="T", paragraphs=["Hi"])
    elif tool_name == "write_xlsx":
        await tool.function(ctx, path="out.xlsx", sheets=[{"name": "S", "rows": [["a"]]}])
    elif tool_name == "write_pdf":
        await tool.function(ctx, path="out.pdf", title="T", sections=[{"body": "Hi"}])
    else:
        await tool.function(
            ctx,
            name="note.md",
            mime_type="text/markdown",
            content_markdown="# Hi",
        )

    assert len(gate.effect_calls) == 1
    assert gate.effect_calls[0].tool_name == tool_name


@pytest.mark.asyncio
async def test_publish_artifact_calls_request_effect(
    tmp_path: Path,
) -> None:
    plugin_dir = tmp_path / "plugins" / "workproba.projet"
    plugin_dir.mkdir(parents=True)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "rapport.docx").write_bytes(b"PK")
    project = storage.create_project(plugin_dir, "Beta")

    gate = RecordingGate()
    deps = _deps(
        project_root=workspace,
        gate=gate,
        plugin_data_dir=plugin_dir,
    )
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_ID])
    tool = agent._function_toolset.tools["publish_artifact"]
    ctx = _ctx(deps)

    await tool.function(
        ctx,
        project_id=project["id"],
        name="rapport.docx",
        source_path="rapport.docx",
    )

    assert len(gate.effect_calls) == 1
    assert gate.effect_calls[0].effect == "publish"


@pytest.mark.asyncio
async def test_read_document_does_not_call_request_effect(tmp_path: Path) -> None:
    gate = RecordingGate()
    client = FakeProjectClient(documents={"a.txt": "hello"})
    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s1",
            documents=[],
            project_root=tmp_path,
            locale="fr",
        ),
        project_client=client,
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
        confirmation_gate=gate,
    )
    agent = build_agent(TestModel())
    tool = agent._function_toolset.tools["read_document"]
    ctx = _ctx(deps)

    await tool.function(ctx, document_id="a.txt")
    assert gate.effect_calls == []


def test_generate_document_persists_via_gate_path(tmp_path: Path) -> None:
    """generate_document écrit un fichier via _persist_binary_document (gated)."""
    gate = RecordingGate()
    deps = _deps(project_root=tmp_path, gate=gate)

    async def run() -> None:
        agent = build_agent(TestModel())
        tool = agent._function_toolset.tools["generate_document"]
        ctx = _ctx(deps)
        await tool.function(
            ctx,
            name="note.md",
            mime_type="text/markdown",
            content_markdown="# Title",
        )

    asyncio.run(run())
    assert len(gate.effect_calls) == 1
    assert gate.effect_calls[0].tool_name == "generate_document"
