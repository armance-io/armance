"""G9 — GET /providers (live catalogue, 60s cache).

The route already exists (providers.py, spec C.9).
G9 adds tests for the G admin-epic perspective:
  - No API key configured → empty catalogue + hint.
  - Key configured → catalogue returned (mocked discovery).
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_providers_no_key_returns_hint(client: AsyncClient) -> None:
    """Without any provider key, discovery should return empty + hint."""
    with patch(
        "armance.web.backend.routes.providers._discover_serialised",
        new=AsyncMock(return_value={}),
    ):
        resp = await client.get("/providers")

    assert resp.status_code == 200
    body = resp.json()
    assert body["providers"] == {}


@pytest.mark.asyncio
async def test_providers_with_key_returns_catalogue(client: AsyncClient) -> None:
    """With a key, the catalogue comes back non-empty."""
    fake = {
        "openrouter": [
            {"id": "gpt-4o-mini", "provider": "openrouter", "tier": "low"},
        ]
    }
    with patch(
        "armance.web.backend.routes.providers._discover_serialised",
        new=AsyncMock(return_value=fake),
    ):
        resp = await client.get("/providers")

    assert resp.status_code == 200
    body = resp.json()
    assert "openrouter" in body["providers"]
    assert len(body["providers"]["openrouter"]) == 1
