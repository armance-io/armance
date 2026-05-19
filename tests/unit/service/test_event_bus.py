"""Tests for service/events.py — EventBus protocol + LocalEventBus."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from armance.service.event_helpers import generate_span_id, generate_trace_id, span
from armance.service.events import LocalEventBus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bus(tmp_path: Path) -> LocalEventBus:
    log_path = tmp_path / "sessions" / "test-sid" / "events.log"
    log_path.parent.mkdir(parents=True)
    return LocalEventBus(log_path=log_path)


# ---------------------------------------------------------------------------
# LocalEventBus — basic emission
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_emit_writes_json_line(tmp_path: Path) -> None:
    bus = _make_bus(tmp_path)
    await bus.emit("workflow.run.started", attributes={"run_id": "r_test"})
    lines = bus.log_path.read_text().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["name"] == "workflow.run.started"
    assert event["attributes"]["run_id"] == "r_test"


@pytest.mark.asyncio
async def test_emit_multiple_lines(tmp_path: Path) -> None:
    bus = _make_bus(tmp_path)
    await bus.emit("workflow.run.started", attributes={})
    await bus.emit("workflow.step.completed", attributes={"step_id": "judge"})
    lines = bus.log_path.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["name"] == "workflow.step.completed"


@pytest.mark.asyncio
async def test_events_log_is_valid_jsonl(tmp_path: Path) -> None:
    bus = _make_bus(tmp_path)
    for name in ["workflow.run.started", "workflow.step.completed", "claim.appended"]:
        await bus.emit(name, attributes={})
    for line in bus.log_path.read_text().splitlines():
        obj = json.loads(line)
        assert "trace_id" in obj
        assert "span_id" in obj
        assert "name" in obj
        assert "timestamp" in obj


# ---------------------------------------------------------------------------
# Span propagation — trace_id inheritance + parent_span_id chaining
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nested_spans_share_trace_id(tmp_path: Path) -> None:
    bus = _make_bus(tmp_path)

    async def run() -> None:
        with span("workflow.run", attributes={"run_id": "r_x"}) as outer:
            await bus.emit("workflow.run.started", attributes={"run_id": "r_x"}, _span=outer)
            with span("workflow.step", attributes={"step_id": "judge"}) as inner:
                await bus.emit("workflow.step.completed", attributes={}, _span=inner)

    await run()

    lines = bus.log_path.read_text().splitlines()
    assert len(lines) == 2
    e1 = json.loads(lines[0])
    e2 = json.loads(lines[1])

    # Same trace
    assert e1["trace_id"] == e2["trace_id"]
    # Inner has outer's span_id as parent
    assert e2["parent_span_id"] == e1["span_id"]
    assert e1["parent_span_id"] is None


@pytest.mark.asyncio
async def test_concurrent_emits_do_not_corrupt_log(tmp_path: Path) -> None:
    bus = _make_bus(tmp_path)

    async def emit_batch(tag: str) -> None:
        for i in range(5):
            await bus.emit("workflow.run.started", attributes={"tag": tag, "i": i})

    await asyncio.gather(emit_batch("A"), emit_batch("B"))

    lines = bus.log_path.read_text().splitlines()
    assert len(lines) == 10
    for line in lines:
        json.loads(line)  # must parse without error


# ---------------------------------------------------------------------------
# TUI queue subscription
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_emit_puts_event_in_queue(tmp_path: Path) -> None:
    bus = _make_bus(tmp_path)
    await bus.emit("workflow.run.started", attributes={"run_id": "r_q"})
    event = bus.queue.get_nowait()
    assert event.name == "workflow.run.started"


# ---------------------------------------------------------------------------
# event_helpers
# ---------------------------------------------------------------------------

def test_generate_trace_id_is_16_hex() -> None:
    tid = generate_trace_id()
    assert len(tid) == 16
    int(tid, 16)  # raises if not hex


def test_generate_span_id_is_8_hex() -> None:
    sid = generate_span_id()
    assert len(sid) == 8
    int(sid, 16)


def test_generate_ids_are_unique() -> None:
    ids = {generate_trace_id() for _ in range(50)}
    assert len(ids) == 50
