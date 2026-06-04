"""GET /projects/{pid}/sessions/{sid}/messages — conversation history.

The web chat loads the existing dialogue on mount (TUI parity), so the
endpoint returns the session's conversation turns oldest-first.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_messages_empty_for_new_session(client: AsyncClient) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    resp = await client.get(f"/projects/default/sessions/{sid}/messages")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"messages": []}


@pytest.mark.asyncio
async def test_messages_returns_turns(client: AsyncClient) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    # Seed turns on the SAME in-memory session the endpoint reads (the app
    # instance lives on the client's ASGI transport).
    app_state = client._transport.app.state.app_state  # type: ignore[attr-defined]
    ws = app_state.get(sid)
    ws.ctx.session.conversation.append("user", "Bonjour", agent="Armance")
    ws.ctx.session.conversation.append("assistant", "Bonjour", agent="Armance")

    resp = await client.get(f"/projects/default/sessions/{sid}/messages")
    msgs = resp.json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["agent"] == "Armance"


@pytest.mark.asyncio
async def test_messages_unknown_session_404(client: AsyncClient) -> None:
    resp = await client.get("/projects/default/sessions/nope/messages")
    assert resp.status_code == 404
