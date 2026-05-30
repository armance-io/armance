"""A.2 — POST /projects/{pid}/sessions creates a session.

Acceptance criteria:
- POST /projects/default/sessions returns 201 with {id, project_id}.
- state.json exists in the armance_root/sessions/<sid>/ directory.
- Two calls produce distinct sids.
"""
from __future__ import annotations

import pytest
from pathlib import Path
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_session_returns_201(client: AsyncClient, armance_root: Path) -> None:
    resp = await client.post("/projects/default/sessions")
    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    assert body["project_id"] == "default"


@pytest.mark.asyncio
async def test_create_session_writes_state_json(client: AsyncClient, armance_root: Path) -> None:
    resp = await client.post("/projects/default/sessions")
    assert resp.status_code == 201
    sid = resp.json()["id"]
    state_path = armance_root / "sessions" / sid / "state.json"
    assert state_path.exists(), f"state.json not found at {state_path}"


@pytest.mark.asyncio
async def test_create_session_distinct_sids(client: AsyncClient) -> None:
    r1 = await client.post("/projects/default/sessions")
    r2 = await client.post("/projects/default/sessions")
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]
