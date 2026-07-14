"""Gestion des confirmations d'écriture avant generate_document (P0 D3b)."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from app.agent.effects import EffectProposal, protections_to_dict
from app.agent.work_events import audit_details_with_work_id, work_id_for_turn
from app.audit import log_event
from app.i18n import t
from app.schemas import AgentEvent, ConfirmationRequestEvent, ErrorEvent

ConfirmationDecision = Literal["approve", "deny"]

CONFIRMATION_TIMEOUT_SECONDS = 300.0


@dataclass
class _PendingConfirmation:
    session_id: str
    turn_id: str
    tool_call_id: str
    event: asyncio.Event = field(default_factory=asyncio.Event)
    decision: ConfirmationDecision | None = None


class ConfirmationGate:
    """File d'attente de confirmations pour un tour agent."""

    def __init__(self, *, session_id: str, turn_id: str, locale: str = "fr") -> None:
        self.session_id = session_id
        self.turn_id = turn_id
        self.locale = locale
        self._pending: dict[str, _PendingConfirmation] = {}
        self.event_queue: asyncio.Queue[AgentEvent] = asyncio.Queue()
        self._lock = asyncio.Lock()

    async def _await_decision(
        self,
        confirmation_id: str,
        pending: _PendingConfirmation,
        event: ConfirmationRequestEvent,
    ) -> ConfirmationDecision | None:
        await self.event_queue.put(event)
        try:
            await asyncio.wait_for(pending.event.wait(), timeout=CONFIRMATION_TIMEOUT_SECONDS)
        except TimeoutError:
            self._pending.pop(confirmation_id, None)
            await self.event_queue.put(
                ErrorEvent(
                    code="confirmation_timeout",
                    message=t(self.locale, "loop.confirmation_timeout"),
                )
            )
            return None

        decision = pending.decision
        self._pending.pop(confirmation_id, None)
        return decision

    async def request_write(
        self,
        *,
        tool_call_id: str,
        tool_name: str = "generate_document",
        action: Literal["create", "modify"],
        proposed_path: str,
        human_summary: str,
    ) -> bool:
        """Émet confirmation_request et attend approve/deny. Retourne True si approuvé."""
        async with self._lock:
            confirmation_id = f"cf_{uuid.uuid4().hex[:16]}"
            pending = _PendingConfirmation(
                session_id=self.session_id,
                turn_id=self.turn_id,
                tool_call_id=tool_call_id,
            )
            self._pending[confirmation_id] = pending

            decision = await self._await_decision(
                confirmation_id,
                pending,
                ConfirmationRequestEvent(
                    turn_id=self.turn_id,
                    confirmation_id=confirmation_id,
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    action=action,
                    proposed_path=proposed_path,
                    human_summary=human_summary,
                ),
            )
            return decision == "approve"

    async def request_effect(
        self,
        *,
        tool_call_id: str,
        proposal: EffectProposal,
        audit_app_data_dir: Path | None = None,
        audit_enabled: bool | None = None,
    ) -> bool:
        """Émet confirmation_request enrichi et attend approve/deny."""
        async with self._lock:
            confirmation_id = f"cf_{uuid.uuid4().hex[:16]}"
            pending = _PendingConfirmation(
                session_id=self.session_id,
                turn_id=self.turn_id,
                tool_call_id=tool_call_id,
            )
            self._pending[confirmation_id] = pending

            work_id = work_id_for_turn(self.turn_id)
            if audit_app_data_dir is not None:
                log_event(
                    audit_app_data_dir,
                    "approval.requested",
                    "agent",
                    audit_details_with_work_id(
                        {
                            "effect": proposal.effect,
                            "targets": proposal.targets,
                            "tool_name": proposal.tool_name,
                        },
                        work_id,
                    ),
                    enabled=audit_enabled,
                )

            decision = await self._await_decision(
                confirmation_id,
                pending,
                ConfirmationRequestEvent(
                    turn_id=self.turn_id,
                    confirmation_id=confirmation_id,
                    tool_call_id=tool_call_id,
                    tool_name=proposal.tool_name,
                    action=proposal.action,
                    proposed_path=proposal.proposed_path,
                    human_summary=proposal.human_summary,
                    effect=proposal.effect,
                    targets=list(proposal.targets),
                    protections=protections_to_dict(proposal.protections),
                    headline=proposal.headline,
                    protection_labels=list(proposal.protection_labels),
                ),
            )

            if audit_app_data_dir is not None:
                log_event(
                    audit_app_data_dir,
                    "approval.resolved",
                    "agent",
                    audit_details_with_work_id(
                        {"decision": decision or "timeout"},
                        work_id,
                    ),
                    enabled=audit_enabled,
                )

            return decision == "approve"

    def resolve(self, confirmation_id: str, decision: ConfirmationDecision) -> bool:
        pending = self._pending.get(confirmation_id)
        if pending is None:
            return False
        pending.decision = decision
        pending.event.set()
        return True

    def cancel_all(self) -> None:
        for pending in self._pending.values():
            pending.decision = "deny"
            pending.event.set()
        self._pending.clear()


class ConfirmationRegistry:
    """Registre global (session_id, turn_id) -> gate (pour POST /agent/confirm)."""

    def __init__(self) -> None:
        self._gates: dict[tuple[str, str], ConfirmationGate] = {}
        self._lock = asyncio.Lock()

    async def register(self, gate: ConfirmationGate) -> None:
        async with self._lock:
            self._gates[(gate.session_id, gate.turn_id)] = gate

    async def unregister(self, session_id: str, turn_id: str) -> None:
        async with self._lock:
            self._gates.pop((session_id, turn_id), None)

    def resolve(
        self,
        session_id: str,
        turn_id: str | None,
        confirmation_id: str,
        decision: ConfirmationDecision,
    ) -> bool:
        if turn_id is not None:
            gate = self._gates.get((session_id, turn_id))
            if gate is None:
                return False
            return gate.resolve(confirmation_id, decision)

        # Rétrocompat : sans turn_id, cherche parmi les gates actives de la session.
        for (gate_session_id, _), gate in self._gates.items():
            if gate_session_id != session_id:
                continue
            if gate.resolve(confirmation_id, decision):
                return True
        return False

    def get_gate(self, session_id: str, turn_id: str) -> ConfirmationGate | None:
        return self._gates.get((session_id, turn_id))


confirmation_registry = ConfirmationRegistry()
