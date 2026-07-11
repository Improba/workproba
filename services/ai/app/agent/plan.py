"""Plan mode : proposition et approbation avant tâches complexes."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from app.i18n import t
from app.schemas import AgentEvent, ErrorEvent, PlanProposedEvent, PlanStepInfo

PlanDecision = Literal["approve", "deny"]

PLAN_TIMEOUT_SECONDS = 600.0


@dataclass
class _PendingPlan:
    session_id: str
    turn_id: str
    plan_id: str
    event: asyncio.Event = field(default_factory=asyncio.Event)
    decision: PlanDecision | None = None
    modifications: list[PlanStepInfo] | None = None


class PlanGate:
    """File d'attente de plans pour un tour agent."""

    def __init__(self, *, session_id: str, turn_id: str) -> None:
        self.session_id = session_id
        self.turn_id = turn_id
        self._pending: dict[str, _PendingPlan] = {}
        self.event_queue: asyncio.Queue[AgentEvent] = asyncio.Queue()

    async def request_plan(
        self,
        *,
        steps: list[dict[str, Any]],
        rationale: str,
        locale: str = "fr",
    ) -> dict[str, Any]:
        plan_id = f"plan_{uuid.uuid4().hex[:16]}"
        parsed_steps = [
            PlanStepInfo(
                tool=str(step.get("tool", "")),
                summary=str(step.get("summary", "")),
                target=str(step.get("target", "")),
            )
            for step in steps
            if isinstance(step, dict)
        ]
        pending = _PendingPlan(
            session_id=self.session_id,
            turn_id=self.turn_id,
            plan_id=plan_id,
        )
        self._pending[plan_id] = pending

        await self.event_queue.put(
            PlanProposedEvent(
                session_id=self.session_id,
                plan_id=plan_id,
                steps=parsed_steps,
                rationale=rationale,
            )
        )

        try:
            await asyncio.wait_for(pending.event.wait(), timeout=PLAN_TIMEOUT_SECONDS)
        except TimeoutError:
            self._pending.pop(plan_id, None)
            await self.event_queue.put(
                ErrorEvent(
                    code="plan_timeout",
                    message=t(locale, "plan.timeout"),
                )
            )
            return {"approved": False, "cancelled": True, "reason": "timeout"}

        decision = pending.decision
        modifications = pending.modifications
        self._pending.pop(plan_id, None)

        if decision != "approve":
            return {"approved": False, "cancelled": True, "reason": "denied"}

        result: dict[str, Any] = {"approved": True, "plan_id": plan_id}
        if modifications is not None:
            result["steps"] = [step.model_dump() for step in modifications]
        else:
            result["steps"] = [step.model_dump() for step in parsed_steps]
        return result

    def resolve(
        self,
        plan_id: str,
        *,
        approved: bool,
        modifications: list[PlanStepInfo] | None = None,
    ) -> bool:
        pending = self._pending.get(plan_id)
        if pending is None:
            return False
        pending.decision = "approve" if approved else "deny"
        pending.modifications = modifications
        pending.event.set()
        return True

    def cancel_all(self) -> None:
        for pending in self._pending.values():
            pending.decision = "deny"
            pending.event.set()
        self._pending.clear()


class PlanRegistry:
    """Registre global session_id + turn_id -> PlanGate."""

    def __init__(self) -> None:
        self._gates: dict[tuple[str, str], PlanGate] = {}
        self._lock = asyncio.Lock()

    async def register(self, gate: PlanGate) -> None:
        async with self._lock:
            self._gates[(gate.session_id, gate.turn_id)] = gate

    async def unregister(self, session_id: str, turn_id: str) -> None:
        async with self._lock:
            self._gates.pop((session_id, turn_id), None)

    def resolve(
        self,
        session_id: str,
        turn_id: str | None,
        plan_id: str,
        *,
        approved: bool,
        modifications: list[PlanStepInfo] | None = None,
    ) -> bool:
        if turn_id is not None:
            gate = self._gates.get((session_id, turn_id))
            if gate is None:
                return False
            return gate.resolve(plan_id, approved=approved, modifications=modifications)

        for (gate_session_id, _), gate in self._gates.items():
            if gate_session_id != session_id:
                continue
            if gate.resolve(plan_id, approved=approved, modifications=modifications):
                return True
        return False

    def get_gate(self, session_id: str, turn_id: str) -> PlanGate | None:
        return self._gates.get((session_id, turn_id))


plan_registry = PlanRegistry()
