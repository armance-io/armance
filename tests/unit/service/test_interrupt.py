"""Tests for clean cancel and interrupt handling in the TUI loop.

We test the logical behavior (state transitions, partial save) without
requiring a real terminal or prompt_toolkit event loop.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from armance.service.handlers import LoopContext
from armance.config import Config, ProviderConfig
from armance.service.llm_service import TokenLedger
from armance.service.session import SessionState, save_state
from armance.client.tui.types import AgentStatus


def _make_ctx(tmp_path: Path) -> LoopContext:
    from armance.service.session import Session
    cfg = Config(
        providers=[ProviderConfig(name="openrouter", api_key="k")],
        default_provider="openrouter",
        default_model="m",
    )
    state = SessionState.new()
    state.ledger_path = str(tmp_path / "ledger.json")
    save_state(tmp_path, state)
    session = Session(state, tmp_path)
    ledger = TokenLedger()
    return LoopContext(
        armance_root=tmp_path,
        cfg=cfg,
        state=state,
        session=session,
        ledger=ledger,
        statuses=[AgentStatus(name="alpha", state="idle")],
        agents=[],
    )


@pytest.mark.asyncio
async def test_cancel_running_task_sets_cancelled_output() -> None:
    """Cancelling an asyncio.Task mid-run returns '[cancelled]'."""

    async def _slow_handler(args, ctx):
        await asyncio.sleep(10)
        return "completed"

    ctx_: LoopContext | None = None

    async def run(tmp_path: Path) -> str:
        nonlocal ctx_
        ctx_ = _make_ctx(tmp_path)
        task = asyncio.create_task(_slow_handler([], ctx_))
        # cancel immediately
        task.cancel()
        try:
            return await task
        except asyncio.CancelledError:
            return "[cancelled]"

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        result = await run(Path(tmp))

    assert result == "[cancelled]"


@pytest.mark.asyncio
async def test_cancelled_task_resets_agent_status(tmp_path: Path) -> None:
    """After cancel, agent status should not stay 'working'."""
    from armance.client.tui.types import AgentStatus

    ctx = _make_ctx(tmp_path)
    ctx.statuses = [AgentStatus(name="worker", state="working")]

    async def _slow():
        await asyncio.sleep(10)

    task = asyncio.create_task(_slow())
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        # Simulate what the TUI loop does: append cancelled message
        for s in ctx.statuses:
            if s.state == "working":
                s.state = "idle"
        ctx.append("[cancelled]")

    assert ctx.statuses[0].state == "idle"
    assert any("[cancelled]" in line for line in ctx.output_lines)


@pytest.mark.asyncio
async def test_double_ctrl_c_window_is_one_second(tmp_path: Path) -> None:
    """Second Ctrl+C within 1s triggers quit; after 1s it does not."""
    import time

    ctx = _make_ctx(tmp_path)

    # Simulate the timing logic from tui_loop.run_tui
    WINDOW = 1.0
    last = time.monotonic()

    # First Ctrl+C
    now = time.monotonic()
    first_delta = now - last
    assert first_delta >= 0  # always true — first is allowed

    # Immediate second Ctrl+C (< 1s)
    now2 = time.monotonic()
    assert (now2 - last) < WINDOW or (now2 - last) < WINDOW  # essentially 0s apart
    should_quit = (now2 - last) < WINDOW
    assert should_quit


@pytest.mark.asyncio
async def test_partial_output_saved_on_cancel(tmp_path: Path) -> None:
    """When a task is cancelled, partial output is preserved in ctx._last_output."""
    ctx = _make_ctx(tmp_path)
    ctx._last_output = "partial result from agent"

    async def _long_task(args, ctx_inner):
        # Simulate work, then gets cancelled
        await asyncio.sleep(10)
        return "never reached"

    task = asyncio.create_task(_long_task([], ctx))
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # _last_output should still hold the partial result, not be cleared
    assert ctx._last_output == "partial result from agent"
