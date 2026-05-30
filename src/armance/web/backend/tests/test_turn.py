"""A.5 — POST /projects/{pid}/sessions/{sid}/turn tests.

Acceptance criteria:
1. POST .../turn returns 202 with {ack: true}; dispatch_input was awaited.
2. After the turn completes, the EventBus receives a 'turn_completed' event
   with reply and agent set.
3. Read-along guard: second client_id → 409 read_along_only.
"""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_turn_returns_202(client: AsyncClient) -> None:
    """POST /turn returns 202 immediately."""
    # Create session.
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    with patch(
        "armance.web.backend.routes.turn.dispatch_input",
        new=AsyncMock(return_value=("hello back", "system-context")),
    ):
        resp = await client.post(
            f"/projects/default/sessions/{sid}/turn",
            json={"text": "hello"},
        )
    assert resp.status_code == 202
    assert resp.json()["ack"] is True


@pytest.mark.asyncio
async def test_turn_publishes_turn_completed(client: AsyncClient) -> None:
    """After dispatch_input completes, 'turn_completed' event is published."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    # Re-resolve the app_state from the client's app.
    # We need to access the bus directly.
    app_state = client._transport.app.state.app_state  # type: ignore[attr-defined]
    ws = app_state.get(sid)

    event_received: asyncio.Event = asyncio.Event()
    events = []

    async def _collect():
        while True:
            try:
                evt = await asyncio.wait_for(ws.bus.queue.get(), timeout=1.0)
                events.append(evt)
                if evt.name == "turn.completed":
                    event_received.set()
                    return
            except asyncio.TimeoutError:
                return

    collector = asyncio.create_task(_collect())

    with patch(
        "armance.web.backend.routes.turn.dispatch_input",
        new=AsyncMock(return_value=("great reply", "system-hr")),
    ):
        await client.post(
            f"/projects/default/sessions/{sid}/turn",
            json={"text": "test message"},
        )
        # Give the background task time to run.
        await asyncio.sleep(0.15)

    await asyncio.wait_for(collector, timeout=1.0)
    assert any(e.name == "turn.completed" for e in events)
    completed = next(e for e in events if e.name == "turn.completed")
    assert completed.attributes["reply"] == "great reply"
    assert completed.attributes["agent"] == "system-hr"


@pytest.mark.asyncio
async def test_turn_unknown_session_returns_404(client: AsyncClient) -> None:
    resp = await client.post(
        "/projects/default/sessions/bad-sid/turn",
        json={"text": "hello"},
    )
    assert resp.status_code == 404
