"""Setup route persists optional rerank model fields."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_setup_init_persists_rerank(client: AsyncClient) -> None:
    resp = await client.post("/setup/init", json={
        "provider": "openrouter",
        "api_key": "sk-test",
        "model": "openai/gpt-4o-mini",
        "budget": "optimised",
        "language": "en",
        "embedding_provider": "openrouter",
        "embedding_model": "text-embedding-3-small",
        "rerank_provider": "openrouter",
        "rerank_model": "cohere/rerank-v3.5",
    })
    assert resp.status_code == 201
    from armance.config import load_config
    cfg = load_config()
    assert cfg.rerank_provider == "openrouter"
    assert cfg.rerank_model == "cohere/rerank-v3.5"


@pytest.mark.asyncio
async def test_setup_init_rerank_optional(client: AsyncClient) -> None:
    """Omitting rerank fields leaves rerank off (empty strings)."""
    resp = await client.post("/setup/init", json={
        "provider": "openrouter",
        "api_key": "sk-test",
        "model": "openai/gpt-4o-mini",
        "budget": "optimised",
        "language": "en",
    })
    assert resp.status_code == 201
    from armance.config import load_config
    cfg = load_config()
    assert cfg.rerank_provider == ""
    assert cfg.rerank_model == ""
