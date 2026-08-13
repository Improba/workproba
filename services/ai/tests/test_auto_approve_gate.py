"""Tests for AutoApproveGate (space trust mode)."""

from __future__ import annotations

import asyncio

import pytest

from app.agent.confirmation import AutoApproveGate
from app.agent.effects import EffectProposal
from app.schemas import ConfirmationPreparingEvent, ToolAutoApprovedEvent


@pytest.mark.asyncio
async def test_auto_approve_gate_request_write_immediate() -> None:
    gate = AutoApproveGate(session_id="s1", turn_id="t-auto")

    outcome = await gate.request_write(
        tool_call_id="tc1",
        action="create",
        proposed_path="/tmp/out.txt",
        human_summary="Créer fichier",
    )
    assert outcome == "approved"

    event = await asyncio.wait_for(gate.event_queue.get(), timeout=1.0)
    assert isinstance(event, ToolAutoApprovedEvent)
    assert event.tool_call_id == "tc1"
    assert event.trust_key == "file_write:create"


@pytest.mark.asyncio
async def test_auto_approve_gate_request_effect_immediate() -> None:
    gate = AutoApproveGate(session_id="s1", turn_id="t-auto")
    proposal = EffectProposal(
        effect="external_send",
        tool_name="invoke_managed_connector",
        targets=["pennylane"],
        action="create",
        human_summary="Écriture Pennylane",
    )

    outcome = await gate.request_effect(tool_call_id="tc2", proposal=proposal)
    assert outcome == "approved"

    event = await asyncio.wait_for(gate.event_queue.get(), timeout=1.0)
    assert isinstance(event, ToolAutoApprovedEvent)
    assert event.tool_call_id == "tc2"
    assert event.trust_key == "connector:pennylane"


@pytest.mark.asyncio
async def test_auto_approve_gate_notify_preparing_no_event() -> None:
    gate = AutoApproveGate(session_id="s1", turn_id="t-auto")
    await gate.notify_preparing(
        tool_call_id="tc1",
        tool_name="invoke_managed_connector",
        connector_id="pennylane",
        action="create",
    )

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(gate.event_queue.get(), timeout=0.05)


@pytest.mark.asyncio
async def test_auto_approve_gate_no_confirmation_request() -> None:
    gate = AutoApproveGate(session_id="s1", turn_id="t-auto")
    proposal = EffectProposal(
        effect="create",
        tool_name="generate_document",
        action="create",
        human_summary="Écrire",
    )

    async def consume() -> None:
        event = await gate.event_queue.get()
        assert isinstance(event, ToolAutoApprovedEvent)
        assert not isinstance(event, ConfirmationPreparingEvent)

    consumer = asyncio.create_task(consume())
    outcome = await gate.request_effect(tool_call_id="tc3", proposal=proposal)
    await consumer
    assert outcome == "approved"


@pytest.mark.asyncio
async def test_create_confirmation_gate_trust_with_workspace(tmp_path: Path) -> None:
    from app.agent.confirmation import AutoApproveGate, create_confirmation_gate
    from app.space_policy import set_approval_mode

    set_approval_mode(tmp_path, "trust")
    gate = create_confirmation_gate(
        session_id="s1",
        turn_id="t1",
        workspace_data_dir=tmp_path,
        confirm_before_write=True,
    )
    assert isinstance(gate, AutoApproveGate)


@pytest.mark.asyncio
async def test_create_confirmation_gate_security_with_workspace(tmp_path: Path) -> None:
    from app.agent.confirmation import ConfirmationGate, create_confirmation_gate

    gate = create_confirmation_gate(
        session_id="s1",
        turn_id="t1",
        workspace_data_dir=tmp_path,
        confirm_before_write=False,
    )
    assert type(gate) is ConfirmationGate


def test_create_confirmation_gate_no_workspace_fallback() -> None:
    from app.agent.confirmation import AutoApproveGate, ConfirmationGate, create_confirmation_gate

    auto_gate = create_confirmation_gate(
        session_id="s1",
        turn_id="t1",
        confirm_before_write=False,
    )
    assert isinstance(auto_gate, AutoApproveGate)

    confirm_gate = create_confirmation_gate(
        session_id="s1",
        turn_id="t1",
        confirm_before_write=True,
    )
    assert type(confirm_gate) is ConfirmationGate
