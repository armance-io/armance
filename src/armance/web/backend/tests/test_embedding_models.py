"""GET /embedding-models — cross-provider embedding catalogue route.

Returns embedding-capable models across configured providers for the
admin Configuration form and the setup wizard picker.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_get_embedding_models_returns_list(client: AsyncClient) -> None:
    """GET /embedding-models returns a flat list of embedding models."""
    fake = [
        {"provider": "openrouter", "id": "openai/text-embedding-3-small", "name": "Text Embedding 3 Small", "free": False},
        {"provider": "gemini", "id": "text-embedding-004", "name": "Text Embedding 004", "free": True},
    ]
    with patch(
        "armance.web.backend.routes.embedding_models._discover_embedding",
        new=AsyncMock(return_value=fake),
    ):
        resp = await client.get("/embedding-models")
    assert resp.status_code == 200
    data = resp.json()
    assert data["models"] == fake


@pytest.mark.asyncio
async def test_get_embedding_models_handles_failure(client: AsyncClient) -> None:
    """If discovery raises, the route returns an empty list."""
    with patch(
        "armance.web.backend.routes.embedding_models._discover_embedding",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        resp = await client.get("/embedding-models")
    assert resp.status_code == 200
    assert resp.json() == {"models": []}
