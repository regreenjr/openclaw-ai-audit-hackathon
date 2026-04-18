"""SSE event types and emitter helpers for live agent streaming."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable


@dataclass
class AuditEvent:
    """A single event in the audit stream."""
    type: str  # e.g. "agent.start", "agent.thought", "agent.done", "evidence", "score", "error"
    agent: str = ""  # e.g. "researcher", "D1-strategy", "critic", "orchestrator"
    data: dict[str, Any] = field(default_factory=dict)

    def to_sse(self) -> str:
        payload = {"type": self.type, "agent": self.agent, "data": self.data}
        return f"data: {json.dumps(payload)}\n\n"


class EventBus:
    """Async queue bridge between orchestrator coroutine and SSE response generator."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[AuditEvent | None] = asyncio.Queue()

    async def emit(self, event: AuditEvent) -> None:
        await self._queue.put(event)

    async def close(self) -> None:
        await self._queue.put(None)

    async def stream(self) -> AsyncIterator[AuditEvent]:
        while True:
            ev = await self._queue.get()
            if ev is None:
                return
            yield ev


# Convenience factory — lets callers do `emit("agent.start", agent="D1", data={...})`
EmitFn = Callable[..., "asyncio.Future[None] | Any"]


def make_emitter(bus: EventBus) -> EmitFn:
    async def _emit(type_: str, agent: str = "", **data: Any) -> None:
        await bus.emit(AuditEvent(type=type_, agent=agent, data=data))
    return _emit
