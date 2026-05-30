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


@pytest.mark.asyncio
async def test_get_latest_session_auto_creates_if_none(client: AsyncClient, armance_root: Path) -> None:
    # Remove any existing sessions first
    sessions_root = armance_root / "sessions"
    if sessions_root.exists():
        import shutil
        shutil.rmtree(sessions_root)

    resp = await client.get("/projects/default/sessions/latest")
    assert resp.status_code == 200
    body = resp.json()
    assert "id" in body
    assert body["project_id"] == "default"

    # Second call should return the exact same session
    resp2 = await client.get("/projects/default/sessions/latest")
    assert resp2.status_code == 200
    assert resp2.json()["id"] == body["id"]


@pytest.mark.asyncio
async def test_get_latest_session_returns_latest_post_session(client: AsyncClient) -> None:
    r1 = await client.post("/projects/default/sessions")
    assert r1.status_code == 201
    created_sid = r1.json()["id"]

    resp = await client.get("/projects/default/sessions/latest")
    assert resp.status_code == 200
    assert resp.json()["id"] == created_sid
