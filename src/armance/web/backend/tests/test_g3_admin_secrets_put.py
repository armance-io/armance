"""G3 — PUT /projects/{pid}/admin/secrets/{name} (IP-guarded).

Tests:
  - From 127.0.0.1, valid key: writes to .env, returns 200.
  - From 127.0.0.1, invalid key name: returns 400.
  - From non-loopback: returns 403.
"""
from __future__ import annotations

import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport

from .conftest import AUTH_COOKIES
import os


@pytest.mark.asyncio
async def test_put_secret_writes_env(client: AsyncClient, armance_root: Path) -> None:
    resp = await client.put(
        "/projects/default/admin/secrets/MY_API_KEY",
        json={"value": "secret-value-xyz"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "MY_API_KEY"
    assert body["set"] is True

    env_text = (armance_root / ".env").read_text()
    assert "MY_API_KEY=secret-value-xyz" in env_text


@pytest.mark.asyncio
async def test_put_secret_invalid_key_name(client: AsyncClient, armance_root: Path) -> None:
    resp = await client.put(
        "/projects/default/admin/secrets/bad-key-name",
        json={"value": "val"},
    )

    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_key_name"


@pytest.mark.asyncio
async def test_put_secret_from_non_loopback_forbidden(armance_root: Path) -> None:
    os.environ["ARMANCE_ROOT"] = str(armance_root.parent)
    from armance.web.backend.main import create_app
    from armance.web.backend.state import AppState

    app = create_app()
    app.state.app_state = AppState(armance_root=armance_root)

    async with AsyncClient(
        transport=ASGITransport(app=app, client=("8.8.8.8", 0)),
        base_url="http://test",
        cookies=AUTH_COOKIES,
    ) as remote_client:
        resp = await remote_client.put(
            "/projects/default/admin/secrets/MY_KEY",
            json={"value": "val"},
        )

    assert resp.status_code == 403
    assert resp.json()["error"] == "secrets_localhost_only"


@pytest.mark.asyncio
async def test_put_secret_overwrites_existing(client: AsyncClient, armance_root: Path) -> None:
    (armance_root / ".env").write_text("MY_KEY=old_value\n", encoding="utf-8")

    resp = await client.put(
        "/projects/default/admin/secrets/MY_KEY",
        json={"value": "new_value"},
    )

    assert resp.status_code == 200
    env_text = (armance_root / ".env").read_text()
    assert "MY_KEY=new_value" in env_text
    assert "old_value" not in env_text
