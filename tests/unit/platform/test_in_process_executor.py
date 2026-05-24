"""J.4 — InProcessExecutor tests.

Written RED before implementation exists.  Spec:
issues/features/web-j-platform-abstractions.md § J.4

Acceptance criteria from the spec:
- start(run_spec) returns a RunHandle whose run_id matches the spec's manifest id.
- status(run_id) returns "working" while the task is alive.
- cancel(run_id) returns True and the task is cancelled().
- cancel on unknown run_id returns False.
"""
from __future__ import annotations

import asyncio
import pytest


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def executor():
    from armance.platform.executor import InProcessExecutor
    return InProcessExecutor()


def _make_spec(run_id: str = "test-run-001"):
    from armance.platform.executor import WorkflowRunSpec
    return WorkflowRunSpec(run_id=run_id)


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_returns_run_handle(executor) -> None:
    async def noop() -> None:
        await asyncio.sleep(0)

    handle = await executor.start(_make_spec("run-abc"), coro=noop())
    assert handle.run_id == "run-abc"
    # clean up
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_start_returns_handle_with_run_id(executor) -> None:
    async def noop() -> None:
        await asyncio.sleep(0)

    handle = await executor.start(_make_spec("run-xyz"), coro=noop())
    assert handle.run_id == "run-xyz"
    await asyncio.sleep(0)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_status_working_while_task_alive(executor) -> None:
    event = asyncio.Event()

    async def long_running() -> None:
        await event.wait()

    handle = await executor.start(_make_spec("run-long"), coro=long_running())
    status = await executor.status("run-long")
    assert status == "working"
    event.set()
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_status_completed_after_finish(executor) -> None:
    async def quick() -> None:
        pass

    await executor.start(_make_spec("run-quick"), coro=quick())
    await asyncio.sleep(0.05)  # let the task finish
    status = await executor.status("run-quick")
    assert status == "completed"


@pytest.mark.asyncio
async def test_status_unknown_run_id(executor) -> None:
    status = await executor.status("does-not-exist")
    assert status == "not_found"


# ---------------------------------------------------------------------------
# cancel
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancel_returns_true_for_live_task(executor) -> None:
    event = asyncio.Event()

    async def long_running() -> None:
        await event.wait()

    await executor.start(_make_spec("run-cancel"), coro=long_running())
    result = await executor.cancel("run-cancel")
    assert result is True


@pytest.mark.asyncio
async def test_cancel_task_is_cancelled(executor) -> None:
    event = asyncio.Event()

    async def long_running() -> None:
        await event.wait()

    handle = await executor.start(_make_spec("run-cancel2"), coro=long_running())
    await executor.cancel("run-cancel2")
    await asyncio.sleep(0.05)
    assert handle.task.cancelled()


@pytest.mark.asyncio
async def test_cancel_unknown_returns_false(executor) -> None:
    result = await executor.cancel("nonexistent-run")
    assert result is False


@pytest.mark.asyncio
async def test_cancel_already_done_returns_false(executor) -> None:
    async def quick() -> None:
        pass

    await executor.start(_make_spec("run-done"), coro=quick())
    await asyncio.sleep(0.05)
    result = await executor.cancel("run-done")
    assert result is False
