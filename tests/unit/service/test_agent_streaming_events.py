"""C.8 — `agent_streaming_*` events from SpecialistRunner + meta chat shells.

When an agent starts producing tokens, the runtime emits:
  - `agent.streaming.started`  { agent_name, step_id?: str }
  - `agent_streaming`          { agent_name, chunk?: str }  (throttled)
  - `agent.streaming.end`      { agent_name }              (on completion)

When `ctx.event_bus` is None (TUI), emissions are no-ops.

The frontend (BottomSpinner + MessageBubble.streaming) consumes these
events to pulse the per-agent spinner only while tokens are flowing.

Spec: web-c-deliberation.md § C.8
       workflow-live-pipeline.md Phase 2
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from armance.service.agents._streaming_bridge import (
    AgentStreamingEmitter,
    bridge_on_token,
)


@pytest.mark.asyncio
async def test_emitter_emits_started_and_end_with_no_tokens() -> None:
    """Calling start() then end() emits the two bookend events even if
    no token chunk fired in between (zero-token completion)."""
    bus = MagicMock()
    bus.emit = AsyncMock()
    emitter = AgentStreamingEmitter(bus=bus, agent_name="Aisha")
    await emitter.start()
    await emitter.end()
    names = [c.args[0] for c in bus.emit.await_args_list]
    assert names == ["agent.streaming.started", "agent.streaming.end"]
    # Every event carries agent_name.
    for call in bus.emit.await_args_list:
        attrs = call.kwargs.get("attributes") or {}
        assert attrs.get("agent_name") == "Aisha"


@pytest.mark.asyncio
async def test_emitter_throttles_streaming_events() -> None:
    """Many on_token() calls between start/end → at most a few
    `agent_streaming` events (throttled), not one per chunk."""
    bus = MagicMock()
    bus.emit = AsyncMock()
    emitter = AgentStreamingEmitter(bus=bus, agent_name="Aisha", min_interval=0.05)
    await emitter.start()
    for _ in range(50):
        await emitter.on_token("x")
    await emitter.end()

    names = [c.args[0] for c in bus.emit.await_args_list]
    streaming_count = sum(1 for n in names if n == "agent.streaming")
    # 50 tokens in zero wall-clock → at most 1 throttled emit + the bookends.
    assert streaming_count <= 2
    assert names[0] == "agent.streaming.started"
    assert names[-1] == "agent.streaming.end"


@pytest.mark.asyncio
async def test_emitter_no_op_when_bus_none() -> None:
    """No bus, no calls. Used by the TUI path."""
    emitter = AgentStreamingEmitter(bus=None, agent_name="Aisha")
    await emitter.start()
    await emitter.on_token("a")
    await emitter.on_token("b")
    await emitter.end()
    # No assertion — no bus to assert on. Must not raise.


def test_bridge_on_token_wraps_existing_callback() -> None:
    """bridge_on_token returns a sync callable that both forwards to the
    original on_token and schedules the emitter's on_token."""
    forwarded: list[str] = []

    def original(tok: str) -> None:
        forwarded.append(tok)

    bus = MagicMock()
    bus.emit = AsyncMock()
    emitter = AgentStreamingEmitter(bus=bus, agent_name="Aisha")
    wrapped = bridge_on_token(original=original, emitter=emitter)

    # Sync invocation (LLMClient calls this synchronously per chunk).
    wrapped("hello")
    wrapped("world")
    assert forwarded == ["hello", "world"]


def test_bridge_on_token_without_original() -> None:
    """When original is None, the wrapper still works."""
    bus = MagicMock()
    bus.emit = AsyncMock()
    emitter = AgentStreamingEmitter(bus=bus, agent_name="Aisha")
    wrapped = bridge_on_token(original=None, emitter=emitter)
    # Sync invocation must not raise.
    wrapped("hello")
