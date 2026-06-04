"""G4 — DELETE /projects/{pid}/admin/secrets/{name} (IP-guarded).

Tests:
  - From 127.0.0.1: removes key from .env, returns 200 {"deleted": true}.
  - Key not present: returns 200 {"deleted": false}.
  - From non-loopback: returns 403.
"""
from __future__ import annotations

import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport
import os


@pytest.mark.asyncio
async def test_delete_secret_removes_key(client: AsyncClient, armance_root: Path) -> None:
    (armance_root / ".env").write_text("MY_KEY=val\nOTHER=x\n", encoding="utf-8")

    resp = await client.delete("/projects/default/admin/secrets/MY_KEY")

    assert resp.status_code == 200
    assert resp.json()["deleted"] is True

    env_text = (armance_root / ".env").read_text()
    assert "MY_KEY" not in env_text
    assert "OTHER=x" in env_text


@pytest.mark.asyncio
async def test_delete_secret_key_not_present(client: AsyncClient, armance_root: Path) -> None:
    (armance_root / ".env").write_text("OTHER=x\n", encoding="utf-8")

    resp = await client.delete("/projects/default/admin/secrets/MISSING_KEY")

    assert resp.status_code == 200
    assert resp.json()["deleted"] is False


@pytest.mark.asyncio
async def test_delete_secret_from_non_loopback_forbidden(armance_root: Path) -> None:
    os.environ["ARMANCE_ROOT"] = str(armance_root.parent)
    from armance.web.backend.main import create_app
    from armance.web.backend.state import AppState

    app = create_app()
    app.state.app_state = AppState(armance_root=armance_root)

    async with AsyncClient(
        transport=ASGITransport(app=app, client=("8.8.8.8", 0)),
        base_url="http://test",
    ) as remote_client:
        resp = await remote_client.delete("/projects/default/admin/secrets/MY_KEY")

    assert resp.status_code == 403
    assert resp.json()["error"] == "secrets_localhost_only"
