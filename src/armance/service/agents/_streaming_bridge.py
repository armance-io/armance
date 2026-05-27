"""C.8 — Bridge token-stream callbacks to web agent_streaming events.

Wraps the existing `on_token(str)` callback used by SpecialistRunner +
meta-agent chat shells. Emits:

  agent_streaming_started   { agent_name }
  agent_streaming            { agent_name }   (throttled per `min_interval`)
  agent_streaming_end        { agent_name }

When no event_bus is wired (TUI path), the emitter is a no-op.

Spec: web-c-deliberation.md § C.8
       workflow-live-pipeline.md Phase 2
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)


class AgentStreamingEmitter:
    """Emit agent_streaming_* events on an EventBus.

    Use::

        emitter = AgentStreamingEmitter(bus=ctx.event_bus, agent_name=agent.name)
        await emitter.start()
        on_token = bridge_on_token(original=on_token, emitter=emitter)
        # ... call LLM with on_token=on_token ...
        await emitter.end()

    The emitter is safe to instantiate with ``bus=None`` (TUI path):
    every method becomes a no-op.
    """

    def __init__(
        self,
        bus: Any | None,
        agent_name: str,
        min_interval: float = 0.5,
    ) -> None:
        self._bus = bus
        self._agent = agent_name
        self._min_interval = min_interval
        self._last_emit_ts = 0.0

    async def start(self) -> None:
        if self._bus is None:
            return
        try:
            await self._bus.emit(
                "agent_streaming_started",
                attributes={"agent_name": self._agent},
            )
        except Exception:
            logger.exception("agent_streaming_started emit failed")

    async def on_token(self, _chunk: str) -> None:
        if self._bus is None:
            return
        now = time.monotonic()
        if (now - self._last_emit_ts) < self._min_interval:
            return
        self._last_emit_ts = now
        try:
            await self._bus.emit(
                "agent_streaming",
                attributes={"agent_name": self._agent},
            )
        except Exception:
            logger.exception("agent_streaming emit failed")

    async def end(self) -> None:
        if self._bus is None:
            return
        try:
            await self._bus.emit(
                "agent_streaming_end",
                attributes={"agent_name": self._agent},
            )
        except Exception:
            logger.exception("agent_streaming_end emit failed")


def bridge_on_token(
    original: Callable[[str], None] | None,
    emitter: AgentStreamingEmitter,
) -> Callable[[str], None]:
    """Wrap a synchronous on_token callback so each chunk also feeds the emitter.

    The returned callable is synchronous (LLMClient invokes it per chunk
    without awaiting). It schedules the async emit on the running loop;
    if no loop is running, the schedule is skipped — the emit is
    best-effort, never blocking the chat.
    """

    def _wrapped(chunk: str) -> None:
        if original is not None:
            try:
                original(chunk)
            except Exception:
                logger.exception("original on_token raised")
        # Best-effort async dispatch; never block the LLM stream.
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(emitter.on_token(chunk))

    return _wrapped
