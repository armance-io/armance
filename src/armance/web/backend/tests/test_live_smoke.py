from __future__ import annotations

import pytest
from pathlib import Path
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_backend_live_smoke(client: AsyncClient, armance_root: Path) -> None:
    # 1. POST /api/projects/default/sessions
    resp = await client.post("/api/projects/default/sessions")
    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    assert body["project_id"] == "default"
    sid = body["id"]

    # 2. GET /api/projects/default/sessions/latest
    resp_latest = await client.get("/api/projects/default/sessions/latest")
    assert resp_latest.status_code == 200
    body_latest = resp_latest.json()
    assert body_latest["id"] == sid

    # 3. GET /api/projects/default/sessions/{sid}
    resp_session = await client.get(f"/api/projects/default/sessions/{sid}")
    assert resp_session.status_code == 200
    body_session = resp_session.json()
    assert "state" in body_session
    assert "agents" in body_session
    assert len(body_session["agents"]) > 0

    # 4. GET /api/projects/default/admin/config
    resp_config = await client.get("/api/projects/default/admin/config")
    assert resp_config.status_code == 200
    body_config = resp_config.json()
    assert "default_provider" in body_config

    # 5. GET /api/projects/default/admin/secrets (mocked loopback headers)
    # Fastapi depends on localhost-only check, let's pass loopback Host
    resp_secrets = await client.get(
        "/api/projects/default/admin/secrets",
        headers={"Host": "127.0.0.1"}
    )
    assert resp_secrets.status_code == 200

    # 6. GET /api/projects/default/admin/logs
    resp_logs = await client.get("/api/projects/default/admin/logs")
    assert resp_logs.status_code == 200

    # 7. GET /api/projects/default/admin/stats
    resp_stats = await client.get("/api/projects/default/admin/stats")
    assert resp_stats.status_code == 200

    # 8. GET /api/projects/default/sessions/{sid}/agents
    resp_agents = await client.get(f"/api/projects/default/sessions/{sid}/agents")
    assert resp_agents.status_code == 200

    # 9. GET /api/projects/default/admin/footprint?group_by=agent
    resp_footprint = await client.get("/api/projects/default/admin/footprint?group_by=agent")
    assert resp_footprint.status_code == 200
