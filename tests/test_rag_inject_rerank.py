from __future__ import annotations

import logging

import pytest

from armance.config import Config
from armance.core.protocols.llm import RerankHit
from armance.service.agents import _rag_inject


class _Chunk:
    def __init__(self, cid, text):
        self.id, self.text, self.source = cid, text, "doc"


class _FakeClient:
    def __init__(self, order):
        self._order = order

    async def rerank(self, query, documents, model, *, top_n=None):
        return [RerankHit(index=i, score=float(len(documents) - n))
                for n, i in enumerate(self._order)]


@pytest.mark.asyncio
async def test_rerank_chunks_reorders_and_truncates(monkeypatch):
    cands = [_Chunk(i, f"t{i}") for i in range(5)]
    cfg = Config(rerank_provider="openrouter", rerank_model="m", rerank_keep_n=2)
    monkeypatch.setattr(_rag_inject, "get_client", lambda p, c: _FakeClient([3, 1, 0, 2, 4]))
    out = await _rag_inject._rerank_chunks("q", cands, cfg)
    assert [c.id for c in out] == [3, 1]   # reranker order, truncated to keep_n


@pytest.mark.asyncio
async def test_rerank_chunks_degrades_on_error(monkeypatch, caplog):
    cands = [_Chunk(i, f"t{i}") for i in range(4)]
    cfg = Config(rerank_provider="openrouter", rerank_model="m", rerank_keep_n=2)

    class _Boom:
        async def rerank(self, *a, **k):
            raise RuntimeError("5xx")

    monkeypatch.setattr(_rag_inject, "get_client", lambda p, c: _Boom())
    with caplog.at_level(logging.WARNING):
        out = await _rag_inject._rerank_chunks("q", cands, cfg)
    assert [c.id for c in out] == [0, 1]   # vector order, keep_n, no raise


@pytest.mark.asyncio
async def test_rerank_chunks_tiny_corpus(monkeypatch):
    cands = [_Chunk(0, "t0")]
    cfg = Config(rerank_provider="openrouter", rerank_model="m", rerank_keep_n=5)
    monkeypatch.setattr(_rag_inject, "get_client", lambda p, c: _FakeClient([0]))
    out = await _rag_inject._rerank_chunks("q", cands, cfg)
    assert [c.id for c in out] == [0]      # all, no crash
