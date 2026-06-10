"""Static bundle assets must be served BEFORE the auth gate.

Regression: on the first page load via ?token, the HTML nav authenticates but
the follow-up /_next/* chunk fetches (Accept: */*, no cookie yet) were 401'd by
the gate → blank page. Bundle assets are public (hashed, no user data); only
data routes stay gated.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture()
async def client_with_bundle(tmp_path: Path, monkeypatch):
    """A client whose app serves a minimal fake static export."""
    static = tmp_path / "out"
    (static / "_next" / "static" / "chunks").mkdir(parents=True)
    (static / "index.html").write_text("<html>shell</html>", encoding="utf-8")
    (static / "launcher.html").write_text("<html>launcher</html>", encoding="utf-8")
    (static / "_next" / "static" / "chunks" / "app.js").write_text(
        "console.log('chunk')", encoding="utf-8"
    )
    monkeypatch.setenv("ARMANCE_WEB_DIST", str(static))

    from armance.web.backend.main import create_app
    from armance.web.backend.state import AppState

    app = create_app()
    app.state.app_state = AppState(armance_root=tmp_path / ".armance")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:  # NO auth cookie — first-load conditions
        yield ac


@pytest.mark.asyncio
async def test_next_chunk_served_ungated(client_with_bundle: AsyncClient) -> None:
    resp = await client_with_bundle.get("/_next/static/chunks/app.js")
    assert resp.status_code == 200
    assert "chunk" in resp.text


@pytest.mark.asyncio
async def test_html_shell_served_ungated(client_with_bundle: AsyncClient) -> None:
    resp = await client_with_bundle.get("/launcher", headers={"accept": "text/html"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_data_route_still_gated(client_with_bundle: AsyncClient) -> None:
    # No cookie → the gate must still reject a data route.
    resp = await client_with_bundle.get("/api/launcher")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_no_path_traversal_via_static(client_with_bundle: AsyncClient) -> None:
    # A traversal attempt must not escape the bundle dir.
    resp = await client_with_bundle.get("/_next/../../../../etc/passwd")
    assert resp.status_code in (401, 404)
