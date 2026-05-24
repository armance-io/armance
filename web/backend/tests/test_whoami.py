"""A.1 — GET /whoami returns {user: "local"} with Depends(get_current_user)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_whoami_local(client: AsyncClient) -> None:
    resp = await client.get("/whoami")
    assert resp.status_code == 200
    assert resp.json() == {"user": "local"}
