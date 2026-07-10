"""Gestion des confirmations d'écriture avant generate_document (P0 D3b)."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Literal

from app.schemas import AgentEvent, ConfirmationRequestEvent

ConfirmationDecision = Literal["approve", "deny"]

CONFIRMATION_TIMEOUT_SECONDS = 300.0


@dataclass
class _PendingConfirmation:
    session_id: str
    tool_call_id: str
    event: asyncio.Event = field(default_factory=asyncio.Event)
    decision: ConfirmationDecision | None = None


class ConfirmationGate:
    """File d'attente de confirmations pour un tour agent."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._pending: dict[str, _PendingConfirmation] = {}
        self.event_queue: asyncio.Queue[AgentEvent] = asyncio.Queue()

    async def request_write(
        self,
        *,
        tool_call_id: str,
        action: Literal["create", "modify"],
        proposed_path: str,
        human_summary: str,
    ) -> bool:
        """Émet confirmation_request et attend approve/deny. Retourne True si approuvé."""
        confirmation_id = f"cf_{uuid.uuid4().hex[:16]}"
        pending = _PendingConfirmation(
            session_id=self.session_id,
            tool_call_id=tool_call_id,
        )
        self._pending[confirmation_id] = pending

        await self.event_queue.put(
            ConfirmationRequestEvent(
                confirmation_id=confirmation_id,
                tool_call_id=tool_call_id,
                tool_name="generate_document",
                action=action,
                proposed_path=proposed_path,
                human_summary=human_summary,
            )
        )

        try:
            await asyncio.wait_for(pending.event.wait(), timeout=CONFIRMATION_TIMEOUT_SECONDS)
        except TimeoutError:
            self._pending.pop(confirmation_id, None)
            return False

        decision = pending.decision
        self._pending.pop(confirmation_id, None)
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
    """Registre global session_id -> gate (pour POST /agent/confirm)."""

    def __init__(self) -> None:
        self._gates: dict[str, ConfirmationGate] = {}
        self._lock = asyncio.Lock()

    async def register(self, gate: ConfirmationGate) -> None:
        async with self._lock:
            self._gates[gate.session_id] = gate

    async def unregister(self, session_id: str) -> None:
        async with self._lock:
            self._gates.pop(session_id, None)

    def resolve(
        self,
        session_id: str,
        confirmation_id: str,
        decision: ConfirmationDecision,
    ) -> bool:
        gate = self._gates.get(session_id)
        if gate is None:
            return False
        return gate.resolve(confirmation_id, decision)


confirmation_registry = ConfirmationRegistry()
