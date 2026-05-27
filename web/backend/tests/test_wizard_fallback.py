"""A.9 — Wizard fallback: no config.yaml → 409 not_initialised.

When armance web is started in a directory without .armance/config.yaml,
GET /healthz still answers 200 (the server is up), but any attempt to
create a session returns 409 {error: not_initialised, redirect: /setup}.
"""
from __future__ import annotations

import os
import pytest
import pytest_asyncio
from pathlib import Path
from httpx import AsyncClient, ASGITransport


@pytest.fixture()
def uninitialised_root(tmp_path: Path) -> Path:
    """An armance_root WITHOUT a config.yaml (not initialised)."""
    root = tmp_path / ".armance"
    root.mkdir()
    # Deliberately no config.yaml.
    return root


@pytest_asyncio.fixture()
async def uninit_client(uninitialised_root: Path) -> AsyncClient:
    """Test client with an uninitialised project directory."""
    os.environ["ARMANCE_ROOT"] = str(uninitialised_root.parent)
    from backend.main import create_app
    from backend.state import AppState
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        app.state.app_state = AppState(armance_root=uninitialised_root)
        yield ac
    os.environ.pop("ARMANCE_ROOT", None)


@pytest.mark.asyncio
async def test_healthz_always_responds(uninit_client: AsyncClient) -> None:
    """GET /healthz returns 200 even when the project is not initialised."""
    resp = await uninit_client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


@pytest.mark.asyncio
async def test_create_session_not_initialised_returns_409(uninit_client: AsyncClient) -> None:
    """POST /sessions returns 409 with not_initialised + /setup redirect."""
    resp = await uninit_client.post("/projects/default/sessions")
    assert resp.status_code == 409
    body = resp.json()
    assert body["detail"]["error"] == "not_initialised"
    assert body["detail"]["redirect"] == "/setup"
