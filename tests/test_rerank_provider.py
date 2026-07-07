from __future__ import annotations

import json

import httpx
import pytest
import respx

from armance.config import ProviderConfig
from armance.core.protocols.llm import RerankHit
from armance.providers.openrouter import OpenRouterClient


@pytest.mark.asyncio
async def test_openrouter_rerank_maps_results_sorted():
    cfg = ProviderConfig(name="openrouter", api_key="k",
                         base_url="https://openrouter.ai/api/v1")
    client = OpenRouterClient(cfg)
    payload = {
        "results": [
            {"index": 0, "relevance_score": 0.2},
            {"index": 1, "relevance_score": 0.9},
            {"index": 2, "relevance_score": 0.5},
        ],
        "usage": {"total_tokens": 42},
        "model": "cohere/rerank-v3.5",
    }
    with respx.mock:
        respx.post("https://openrouter.ai/api/v1/rerank").mock(
            return_value=httpx.Response(200, json=payload)
        )
        hits = await client.rerank("q", ["a", "b", "c"], "cohere/rerank-v3.5", top_n=3)
    assert [h.index for h in hits] == [1, 2, 0]      # sorted by score desc
    assert isinstance(hits[0], RerankHit)
    assert hits[0].score == 0.9


@pytest.mark.asyncio
async def test_openrouter_rerank_sends_expected_body():
    cfg = ProviderConfig(name="openrouter", api_key="k",
                         base_url="https://openrouter.ai/api/v1")
    client = OpenRouterClient(cfg)
    captured = {}

    def _capture(request):
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"results": [{"index": 0, "relevance_score": 1.0}]})

    with respx.mock:
        respx.post("https://openrouter.ai/api/v1/rerank").mock(side_effect=_capture)
        await client.rerank("hello", ["d0", "d1"], "m", top_n=2)
    assert captured["model"] == "m"
    assert captured["query"] == "hello"
    assert captured["documents"] == ["d0", "d1"]
    assert captured["top_n"] == 2


@pytest.mark.asyncio
async def test_default_rerank_raises():
    from armance.providers.claude_code import ClaudeCodeClient
    cfg = ProviderConfig(name="claude-code")
    client = ClaudeCodeClient(cfg)
    with pytest.raises(NotImplementedError):
        await client.rerank("q", ["a"], "m")
