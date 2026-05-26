"""C.9 — GET /providers — live catalogue route.

Returns the model catalogue per configured provider for the
ModelSwitcher control. Cached at the provider-discovery layer so
repeated calls during the same session don't hammer the providers.

Spec: web-c-deliberation.md § C.9
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_get_providers_returns_catalogue(client: AsyncClient) -> None:
    """GET /providers returns a JSON dict with one entry per provider."""
    fake_catalogue = {
        "openrouter": [
            {
                "id": "google/gemma-2-9b-it:free",
                "provider": "openrouter",
                "tier": "free",
                "effectively_free": True,
                "context_window": 8192,
                "supports_reasoning": False,
                "supports_vision": False,
                "display_name": "Gemma 2 9B (free)",
            },
            {
                "id": "openai/gpt-4o-mini",
                "provider": "openrouter",
                "tier": "low",
                "effectively_free": False,
                "context_window": 128000,
                "supports_reasoning": False,
                "supports_vision": True,
                "display_name": "GPT-4o mini",
            },
        ],
    }

    with patch(
        "backend.routes.providers._discover_serialised",
        new=AsyncMock(return_value=fake_catalogue),
    ):
        resp = await client.get("/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert "providers" in data
    assert "openrouter" in data["providers"]
    models = data["providers"]["openrouter"]
    assert len(models) == 2
    assert models[0]["id"] == "google/gemma-2-9b-it:free"


@pytest.mark.asyncio
async def test_get_providers_handles_discovery_failure(client: AsyncClient) -> None:
    """If discovery raises, the route returns an empty catalogue + hint."""
    with patch(
        "backend.routes.providers._discover_serialised",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        resp = await client.get("/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["providers"] == {}
    assert "hint" in data
