"""G2 — GET /projects/{pid}/admin/secrets (masked, IP-guarded).

Tests:
  - From 127.0.0.1: returns masked list of known env keys.
  - From non-loopback: returns 403 {"error": "secrets_localhost_only"}.
  - Key with value: set=true, value masked as "sk-***…<last4>".
  - Empty .env: returns empty list.
"""
from __future__ import annotations

import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport

from .conftest import AUTH_COOKIES
import os


def _write_env(armance_root: Path, content: str) -> None:
    (armance_root / ".env").write_text(content, encoding="utf-8")


@pytest.mark.asyncio
async def test_get_secrets_from_loopback(client: AsyncClient, armance_root: Path) -> None:
    _write_env(armance_root, "OPENROUTER_API_KEY=sk-or-v1-abcdef1234\n")

    resp = await client.get("/projects/default/admin/secrets")

    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    entry = next((e for e in body if e["name"] == "OPENROUTER_API_KEY"), None)
    assert entry is not None
    assert entry["set"] is True
    assert entry["value"].startswith("sk-***")
    assert entry["value"].endswith("1234")
    assert "abcdef" not in entry["value"]


@pytest.mark.asyncio
async def test_get_secrets_from_non_loopback_forbidden(armance_root: Path) -> None:
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
        resp = await remote_client.get("/projects/default/admin/secrets")

    assert resp.status_code == 403
    assert resp.json()["error"] == "secrets_localhost_only"


@pytest.mark.asyncio
async def test_get_secrets_empty_env(client: AsyncClient, armance_root: Path) -> None:
    _write_env(armance_root, "")

    resp = await client.get("/projects/default/admin/secrets")

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_secrets_missing_env_file(client: AsyncClient, armance_root: Path) -> None:
    env_path = armance_root / ".env"
    if env_path.exists():
        env_path.unlink()

    resp = await client.get("/projects/default/admin/secrets")

    assert resp.status_code == 200
    assert resp.json() == []
