"""Epic S · security gate — auth on every data route.

Data routers are mounted under both "" and "/api", so the gate covers both
to avoid a prefix-drop bypass. Static HTML navigations are served by the SPA
middleware before the gate, so the login shell stays reachable unauthenticated.
The shared backend `client` fixture carries the session cookie, so the rest
of the suite is unaffected.
"""
from __future__ import annotations

import os

import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from armance.service import security


SECRET = "test-secret-token"


@pytest_asyncio.fixture()
async def secured_client(armance_root, request):
    """Test client with a fixed web password set via env."""
    os.environ["ARMANCE_ROOT"] = str(armance_root.parent)
    os.environ["ARMANCE_WEB_PASSWORD"] = SECRET
    security.reset_web_secret_cache()
    from armance.web.backend.main import create_app
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        from armance.web.backend.state import AppState
        app.state.app_state = AppState(armance_root=armance_root)
        yield ac
    os.environ.pop("ARMANCE_ROOT", None)
    os.environ.pop("ARMANCE_WEB_PASSWORD", None)
    security.reset_web_secret_cache()


async def test_api_health_is_public(secured_client: AsyncClient):
    r = await secured_client.get("/api/healthz")
    assert r.status_code == 200


async def test_api_route_without_credentials_is_401(secured_client: AsyncClient):
    r = await secured_client.get("/api/whoami")
    assert r.status_code == 401


async def test_api_route_with_bearer_header_ok(secured_client: AsyncClient):
    r = await secured_client.get(
        "/api/whoami", headers={"Authorization": f"Bearer {SECRET}"}
    )
    assert r.status_code == 200


async def test_api_route_with_query_token_ok(secured_client: AsyncClient):
    r = await secured_client.get(f"/api/whoami?token={SECRET}")
    assert r.status_code == 200


async def test_api_route_with_cookie_ok(secured_client: AsyncClient):
    secured_client.cookies.set("armance_session_token", SECRET)
    r = await secured_client.get("/api/whoami")
    assert r.status_code == 200
    secured_client.cookies.clear()


async def test_api_route_with_bad_token_is_401(secured_client: AsyncClient):
    r = await secured_client.get("/api/whoami?token=nope")
    assert r.status_code == 401


async def test_root_mounted_data_routes_are_also_gated(secured_client: AsyncClient):
    """Data routes exist at both "" and "/api"; the gate must cover both,
    else an attacker drops the /api prefix to reach an unauthenticated mount."""
    r = await secured_client.get("/whoami")
    assert r.status_code == 401
    r_ok = await secured_client.get(
        "/whoami", headers={"Authorization": f"Bearer {SECRET}"}
    )
    assert r_ok.status_code == 200


async def test_auth_verify_public_and_reports_validity(secured_client: AsyncClient):
    bad = await secured_client.get("/api/auth/verify")
    assert bad.status_code == 401
    ok = await secured_client.get(f"/api/auth/verify?token={SECRET}")
    assert ok.status_code == 200


async def test_auth_login_sets_cookie(secured_client: AsyncClient):
    r = await secured_client.post("/api/auth/login", json={"token": SECRET})
    assert r.status_code == 200
    assert "armance_session_token" in r.cookies
    # And the cookie then authorises a protected call.
    r2 = await secured_client.get("/api/whoami")
    assert r2.status_code == 200


async def test_auth_login_rejects_bad_secret(secured_client: AsyncClient):
    r = await secured_client.post("/api/auth/login", json={"token": "wrong"})
    assert r.status_code == 401
