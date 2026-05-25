"""A.7 — POST /projects/{pid}/sessions/{sid}/checkpoint route.

Acceptance criteria:
1. POST with a registered cp_id → 200 {resolved: true}; pending prompt() resolves.
2. POST with unknown cp_id → 200 {resolved: false}.
"""
from __future__ import annotations

import asyncio
import pytest
from httpx import AsyncClient
from armance.service.checkpoint import Checkpoint


@pytest.mark.asyncio
async def test_checkpoint_resolves_pending_prompt(client: AsyncClient) -> None:
    """POST /checkpoint resolves the pending handler.prompt() future."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    app_state = client._transport.app.state.app_state  # type: ignore[attr-defined]
    ws = app_state.get(sid)

    cp = Checkpoint(id="test-cp", prompt="Ready?", kind="confirm")

    # Start prompt() in background — it will block waiting for resolve.
    prompt_task = asyncio.create_task(ws.handler.prompt(cp))

    # Yield control so the task runs up to its first await (bus.emit).
    # After that, _pending will have one key.
    await asyncio.sleep(0.05)

    # Wait for the checkpoint_requested event so we have the cp_id.
    cp_id: str | None = None
    for _ in range(200):
        if ws.handler._pending:
            cp_id = next(iter(ws.handler._pending))
            break
        await asyncio.sleep(0.01)

    assert cp_id is not None, "checkpoint_id not registered"

    # POST the resolution.
    resp = await client.post(
        f"/projects/default/sessions/{sid}/checkpoint",
        json={"checkpoint_id": cp_id, "content": "yes", "is_abort": False},
    )
    assert resp.status_code == 200
    assert resp.json() == {"resolved": True}

    result = await asyncio.wait_for(prompt_task, timeout=1.0)
    assert result.content == "yes"
    assert result.is_abort is False


@pytest.mark.asyncio
async def test_checkpoint_unknown_id_returns_false(client: AsyncClient) -> None:
    """POST with an unknown checkpoint_id returns {resolved: false}."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    resp = await client.post(
        f"/projects/default/sessions/{sid}/checkpoint",
        json={"checkpoint_id": "no-such-id", "content": "x", "is_abort": False},
    )
    assert resp.status_code == 200
    assert resp.json() == {"resolved": False}


@pytest.mark.asyncio
async def test_checkpoint_unknown_session_returns_404(client: AsyncClient) -> None:
    resp = await client.post(
        "/projects/default/sessions/bad-sid/checkpoint",
        json={"checkpoint_id": "x", "content": "y", "is_abort": False},
    )
    assert resp.status_code == 404
