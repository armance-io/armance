"""GET /projects/{pid}/sessions — list sessions for the header selector.

Newest-first, with turns + token estimate, mirroring the TUI resume picker.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_sessions_empty(client: AsyncClient) -> None:
    resp = await client.get("/projects/default/sessions")
    assert resp.status_code == 200
    assert resp.json() == {"sessions": []}


@pytest.mark.asyncio
async def test_list_sessions_after_create(client: AsyncClient) -> None:
    a = (await client.post("/projects/default/sessions")).json()["id"]
    b = (await client.post("/projects/default/sessions")).json()["id"]

    resp = await client.get("/projects/default/sessions")
    assert resp.status_code == 200
    sessions = resp.json()["sessions"]
    ids = {s["id"] for s in sessions}
    assert {a, b} <= ids
    # Each entry carries the picker fields.
    first = sessions[0]
    assert "id" in first and "updated_at" in first
    assert "turns" in first and "est_tokens" in first
