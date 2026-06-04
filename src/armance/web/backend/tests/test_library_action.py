"""POST /projects/{pid}/sessions/{sid}/library/action — library mutations.

Runs a library action synchronously and returns {ok, message, error} so
the web UI gets a real success/failure signal (no LLM turn).
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_library_action_ok(client: AsyncClient) -> None:
    sid = (await client.post("/projects/default/sessions")).json()["id"]
    with patch(
        "armance.web.backend.routes.library_action.run_library_action",
        new=AsyncMock(return_value={"ok": True, "message": "1 doc · 23 feuillets", "error": None}),
    ):
        resp = await client.post(
            f"/projects/default/sessions/{sid}/library/action",
            json={"action": "index", "name": "doc.pdf"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["error"] is None


@pytest.mark.asyncio
async def test_library_action_surfaces_error(client: AsyncClient) -> None:
    sid = (await client.post("/projects/default/sessions")).json()["id"]
    with patch(
        "armance.web.backend.routes.library_action.run_library_action",
        new=AsyncMock(return_value={"ok": False, "message": "embed init failed", "error": "embed_init_failed"}),
    ):
        resp = await client.post(
            f"/projects/default/sessions/{sid}/library/action",
            json={"action": "index"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["error"] == "embed_init_failed"


@pytest.mark.asyncio
async def test_library_action_unknown_session(client: AsyncClient) -> None:
    resp = await client.post(
        "/projects/default/sessions/nope/library/action",
        json={"action": "index"},
    )
    assert resp.status_code == 404
