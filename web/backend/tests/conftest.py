"""Shared test fixtures for web/backend tests.

Provides an async ASGI test client pre-wired to the FastAPI app.
"""
from __future__ import annotations

import os
import pytest
import pytest_asyncio
from pathlib import Path
from httpx import AsyncClient, ASGITransport


@pytest.fixture()
def armance_root(tmp_path: Path) -> Path:
    """Create a minimal .armance directory for testing."""
    root = tmp_path / ".armance"
    root.mkdir()
    # Create a minimal config.yaml so the sessions route works.
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "language: en\n"
        "model: gpt-4o-mini\n",
        encoding="utf-8",
    )
    return root


@pytest_asyncio.fixture()
async def client(armance_root: Path) -> AsyncClient:
    """Async test client with ARMANCE_ROOT pointed at a temp dir."""
    os.environ["ARMANCE_ROOT"] = str(armance_root.parent)
    from backend.main import create_app
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    os.environ.pop("ARMANCE_ROOT", None)
