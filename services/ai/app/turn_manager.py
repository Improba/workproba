"""Gestion de la concurrence des tours agent par session."""

from __future__ import annotations

import asyncio


class TurnManager:
    """Un seul tour actif par session_id ; les tours concurrents sont refusés."""

    def __init__(self) -> None:
        self._active: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def try_acquire(self, session_id: str, turn_id: str) -> bool:
        async with self._lock:
            if session_id in self._active:
                return False
            self._active[session_id] = turn_id
            return True

    async def release(self, session_id: str, turn_id: str) -> None:
        async with self._lock:
            if self._active.get(session_id) == turn_id:
                self._active.pop(session_id, None)

    def is_active(self, session_id: str) -> bool:
        return session_id in self._active


turn_manager = TurnManager()
