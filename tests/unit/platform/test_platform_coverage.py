"""J.6 — Coverage gap tests for armance.platform.

Covers the lines in platform/ that were not exercised by J.1–J.5 tests:
- event_helpers: span() context manager and current_span()
- events: LocalEventBus with explicit _span kwarg and QueueFull path
- executor: status after failure
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# event_helpers: span() and current_span()
# ---------------------------------------------------------------------------

def test_span_context_manager_sets_trace_id() -> None:
    from armance.platform.event_helpers import span
    with span("test.span") as ctx:
        assert len(ctx.trace_id) == 16
        assert len(ctx.span_id) == 8
        assert ctx.parent_span_id is None


def test_nested_spans_share_trace_id() -> None:
    from armance.platform.event_helpers import span
    with span("outer") as outer:
        with span("inner") as inner:
            assert inner.trace_id == outer.trace_id
            assert inner.parent_span_id == outer.span_id


def test_current_span_inside_context() -> None:
    from armance.platform.event_helpers import current_span, span
    assert current_span() is None
    with span("test") as ctx:
        assert current_span() is ctx
    assert current_span() is None


# ---------------------------------------------------------------------------
# LocalEventBus: explicit _span kwarg (covers events.py:78-80)
# ---------------------------------------------------------------------------

def _make_bus(tmp_path: Path):
    from armance.platform.events import LocalEventBus
    log_path = tmp_path / "events.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    return LocalEventBus(log_path=log_path)


@pytest.mark.asyncio
async def test_emit_with_explicit_span(tmp_path: Path) -> None:
    from armance.platform.event_helpers import SpanContext
    bus = _make_bus(tmp_path)
    ctx = SpanContext(trace_id="a" * 16, span_id="b" * 8, parent_span_id="c" * 8)
    await bus.emit("test.explicit.span", attributes={}, _span=ctx)
    event = json.loads(bus.log_path.read_text().strip())
    assert event["trace_id"] == "a" * 16
    assert event["span_id"] == "b" * 8
    assert event["parent_span_id"] == "c" * 8


@pytest.mark.asyncio
async def test_emit_queue_full_does_not_raise(tmp_path: Path) -> None:
    """When the queue is full, emit should log and not raise."""
    from armance.platform.events import LocalEventBus
    log_path = tmp_path / "events.log"
    bus = LocalEventBus(log_path=log_path)
    # Fill the queue to its maxsize (default is 0 = unlimited in asyncio.Queue,
    # so we instead mock it with a tiny queue to trigger QueueFull)
    import asyncio as _asyncio
    bus.queue = _asyncio.Queue(maxsize=1)
    # Fill it
    bus.queue.put_nowait(object())  # type: ignore[arg-type]
    # Now emit should trigger QueueFull branch gracefully
    await bus.emit("overflow.event", attributes={})


# ---------------------------------------------------------------------------
# InProcessExecutor: failed task status (covers executor.py:120, 122)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_status_failed_after_exception() -> None:
    from armance.platform.executor import InProcessExecutor, WorkflowRunSpec

    executor = InProcessExecutor()

    async def failing() -> None:
        raise ValueError("intentional failure")

    await executor.start(WorkflowRunSpec(run_id="fail-run"), coro=failing())
    await asyncio.sleep(0.05)
    status = await executor.status("fail-run")
    assert status == "failed"


@pytest.mark.asyncio
async def test_status_cancelled_after_cancel(tmp_path: Path) -> None:
    from armance.platform.executor import InProcessExecutor, WorkflowRunSpec

    executor = InProcessExecutor()
    event = asyncio.Event()

    async def long_running() -> None:
        await event.wait()

    await executor.start(WorkflowRunSpec(run_id="cancel-status"), coro=long_running())
    await executor.cancel("cancel-status")
    await asyncio.sleep(0.05)
    status = await executor.status("cancel-status")
    assert status == "cancelled"
