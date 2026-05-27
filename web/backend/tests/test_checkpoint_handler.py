"""A.4 — WebCheckpointHandler tests.

Three acceptance criteria:
1. prompt() blocks until resolve() is called; future resolves with the answer.
2. is_abort=True propagates through to CheckpointResponse.
3. prompt() with no resolve within timeout raises asyncio.TimeoutError.
"""
from __future__ import annotations

import asyncio
import pytest

from armance.service.checkpoint import Checkpoint


@pytest.fixture()
def bus_stub():
    """A minimal event bus stub that records emitted events."""
    class BusStub:
        def __init__(self):
            self.events = []

        async def emit(self, name: str, attributes: dict) -> None:
            self.events.append({"name": name, **attributes})

    return BusStub()


@pytest.fixture()
def handler(bus_stub):
    from backend.checkpoint import WebCheckpointHandler
    return WebCheckpointHandler(bus_stub, timeout=5.0)


@pytest.mark.asyncio
async def test_prompt_resolves_on_resolve(handler, bus_stub) -> None:
    """prompt() blocks until resolve() is called with the matching cp_id."""
    cp = Checkpoint(id="cp1", prompt="Are you sure?", kind="confirm")

    async def _resolve_after_prompt():
        # Wait until the bus has received the checkpoint.requested event.
        for _ in range(50):
            if bus_stub.events:
                break
            await asyncio.sleep(0.01)
        cp_id = bus_stub.events[0]["checkpoint_id"]
        assert handler.resolve(cp_id, "yes")

    asyncio.create_task(_resolve_after_prompt())
    response = await handler.prompt(cp)
    assert response.content == "yes"
    assert response.is_abort is False


@pytest.mark.asyncio
async def test_prompt_propagates_is_abort(handler, bus_stub) -> None:
    """is_abort=True in resolve() → CheckpointResponse.is_abort is True."""
    cp = Checkpoint(id="cp2", prompt="Continue?", kind="confirm")

    async def _abort():
        for _ in range(50):
            if bus_stub.events:
                break
            await asyncio.sleep(0.01)
        cp_id = bus_stub.events[0]["checkpoint_id"]
        handler.resolve(cp_id, "", is_abort=True)

    asyncio.create_task(_abort())
    response = await handler.prompt(cp)
    assert response.is_abort is True


@pytest.mark.asyncio
async def test_prompt_raises_timeout(bus_stub) -> None:
    """prompt() raises asyncio.TimeoutError if not resolved within timeout."""
    from backend.checkpoint import WebCheckpointHandler
    h = WebCheckpointHandler(bus_stub, timeout=0.05)
    cp = Checkpoint(id="cp3", prompt="Never answered", kind="text")
    with pytest.raises(asyncio.TimeoutError):
        await h.prompt(cp)


@pytest.mark.asyncio
async def test_resolve_unknown_cp_id_returns_false(handler) -> None:
    """Resolving an unknown cp_id returns False."""
    assert handler.resolve("unknown-id", "answer") is False


@pytest.mark.asyncio
async def test_resolve_already_done_returns_false(handler, bus_stub) -> None:
    """Resolving the same cp_id twice returns False on the second call."""
    cp = Checkpoint(id="cp5", prompt="?", kind="confirm")

    async def _double_resolve():
        for _ in range(50):
            if bus_stub.events:
                break
            await asyncio.sleep(0.01)
        cp_id = bus_stub.events[0]["checkpoint_id"]
        first = handler.resolve(cp_id, "yes")
        second = handler.resolve(cp_id, "yes")
        assert first is True
        assert second is False

    asyncio.create_task(_double_resolve())
    await handler.prompt(cp)
