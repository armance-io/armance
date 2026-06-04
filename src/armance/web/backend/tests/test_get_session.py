"""A.3 — GET /projects/{pid}/sessions/{sid} returns state + agents + language.

After a POST to create a session, the GET returns 200 with the session's
state, agent list, and language.  Unknown sid → 404.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_session_returns_state(client: AsyncClient) -> None:
    # Create a session first.
    create_resp = await client.post("/projects/default/sessions")
    assert create_resp.status_code == 201
    sid = create_resp.json()["id"]

    resp = await client.get(f"/projects/default/sessions/{sid}")
    assert resp.status_code == 200
    body = resp.json()
    assert "state" in body
    assert "agents" in body
    assert "language" in body
    assert body["language"] == "en"


@pytest.mark.asyncio
async def test_get_session_includes_agents(client: AsyncClient) -> None:
    create_resp = await client.post("/projects/default/sessions")
    sid = create_resp.json()["id"]
    resp = await client.get(f"/projects/default/sessions/{sid}")
    agents = resp.json()["agents"]
    # Should include at least the staff agents (Armance, Malik, Kim, Mona, Serge).
    names = [a["name"] for a in agents]
    assert "system-context" in names
    assert "system-hr" in names


@pytest.mark.asyncio
async def test_get_session_unknown_sid_returns_404(client: AsyncClient) -> None:
    resp = await client.get("/projects/default/sessions/nonexistent-sid")
    assert resp.status_code == 404
