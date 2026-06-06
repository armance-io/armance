"""Shared test fixtures for web/backend tests.

Provides an async ASGI test client pre-wired to the FastAPI app.
The client fixture runs the FastAPI lifespan context so that
app.state.app_state is populated before tests run.
"""
from __future__ import annotations

import os
import pytest
import pytest_asyncio
from pathlib import Path
from httpx import AsyncClient, ASGITransport

# Epic S · security gate. A fixed web password used across the backend suite
# so the gate is deterministic, plus the cookie that authorises a client.
TEST_WEB_SECRET = "test-web-secret"
AUTH_COOKIES = {"armance_session_token": TEST_WEB_SECRET}


@pytest.fixture(autouse=True)
def _web_secret_env(monkeypatch):
    """Pin the gate's secret for every test so it is known and stable."""
    monkeypatch.setenv("ARMANCE_WEB_PASSWORD", TEST_WEB_SECRET)
    from armance.service import security
    security.reset_web_secret_cache()
    yield
    security.reset_web_secret_cache()


@pytest.fixture()
def armance_root(tmp_path: Path) -> Path:
    """Create a minimal .armance directory for testing."""
    root = tmp_path / ".armance"
    root.mkdir()
    # Config lives in .armance/ (same path load_config reads + _check_initialised
    # checks). A provider so the session route can build a client.
    config_path = root / "config.yaml"
    config_path.write_text(
        "language: en\n"
        "default_provider: openrouter\n"
        "default_model: gpt-4o-mini\n"
        "providers:\n"
        "  - name: openrouter\n",
        encoding="utf-8",
    )
    return root


@pytest_asyncio.fixture()
async def client(armance_root: Path, request) -> AsyncClient:
    """Async test client with ARMANCE_ROOT pointed at a temp dir.

    Uses the app's lifespan manager so that app.state.app_state is
    populated before any request is made. The created AppState is also
    stashed so the `app_state` fixture can hand it to tests that call the
    route seams (e.g. _dispatch_run) directly.
    """
    os.environ["ARMANCE_ROOT"] = str(armance_root.parent)
    # Epic S · security gate covers every data route. Carry the session
    # cookie (secret pinned by the autouse _web_secret_env fixture) so tests
    # authenticate transparently.
    from armance.web.backend.main import create_app
    app = create_app()
    # Run the lifespan explicitly via httpx's lifespan support.
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies=AUTH_COOKIES,
    ) as ac:
        # Manually trigger lifespan so app.state.app_state is set.
        from armance.web.backend.state import AppState
        state = AppState(armance_root=armance_root)
        app.state.app_state = state
        request.node._armance_app_state = state
        yield ac
    os.environ.pop("ARMANCE_ROOT", None)


@pytest.fixture()
def app_state(client, request):  # noqa: ARG001 — depend on client for ordering
    """The live AppState created by the `client` fixture (same instance the
    routes use). Lets a test call route seams directly with the real ws."""
    return getattr(request.node, "_armance_app_state", None)
