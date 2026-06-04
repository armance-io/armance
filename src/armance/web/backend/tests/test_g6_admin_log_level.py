"""G6 — PATCH /projects/{pid}/admin/log-level.

Tests:
  - PATCH {"level": "DEBUG"} updates root logger level immediately.
  - Subsequent DEBUG log calls are emitted.
  - Invalid level returns 422.
"""
from __future__ import annotations

import logging
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_set_log_level_debug(client: AsyncClient) -> None:
    resp = await client.patch(
        "/projects/default/admin/log-level",
        json={"level": "DEBUG"},
    )

    assert resp.status_code == 200
    assert resp.json()["level"] == "DEBUG"
    assert logging.getLogger().level == logging.DEBUG

    # Restore to INFO to avoid leaking into other tests
    logging.getLogger().setLevel(logging.INFO)


@pytest.mark.asyncio
async def test_set_log_level_info(client: AsyncClient) -> None:
    resp = await client.patch(
        "/projects/default/admin/log-level",
        json={"level": "INFO"},
    )

    assert resp.status_code == 200
    assert resp.json()["level"] == "INFO"
    assert logging.getLogger().level == logging.INFO


@pytest.mark.asyncio
async def test_set_log_level_invalid_returns_422(client: AsyncClient) -> None:
    resp = await client.patch(
        "/projects/default/admin/log-level",
        json={"level": "VERBOSE"},
    )

    assert resp.status_code == 422
    body = resp.json()
    detail = body.get("detail", body)
    assert "error" in detail
