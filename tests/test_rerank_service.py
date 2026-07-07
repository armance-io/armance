from __future__ import annotations

import logging

import pytest

from armance.config import Config
from armance.core.protocols.llm import RerankHit
from armance.service import rerank as rerank_mod


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
    cfg = Config(rerank_provider="custom-openai", rerank_model="m", rerank_keep_n=2)
    monkeypatch.setattr(rerank_mod, "get_client", lambda p, c: _FakeClient([3, 1, 0, 2, 4]))
    out = await rerank_mod.rerank_chunks("q", cands, cfg)
    assert [c.id for c in out] == [3, 1]   # reranker order, truncated to keep_n


@pytest.mark.asyncio
async def test_rerank_chunks_degrades_on_error(monkeypatch, caplog):
    cands = [_Chunk(i, f"t{i}") for i in range(4)]
    cfg = Config(rerank_provider="custom-openai", rerank_model="m", rerank_keep_n=2)

    class _Boom:
        async def rerank(self, *a, **k):
            raise RuntimeError("5xx")

    monkeypatch.setattr(rerank_mod, "get_client", lambda p, c: _Boom())
    with caplog.at_level(logging.WARNING):
        out = await rerank_mod.rerank_chunks("q", cands, cfg)
    assert [c.id for c in out] == [0, 1]   # vector order, keep_n, no raise


@pytest.mark.asyncio
async def test_rerank_chunks_tiny_corpus(monkeypatch):
    cands = [_Chunk(0, "t0")]
    cfg = Config(rerank_provider="custom-openai", rerank_model="m", rerank_keep_n=5)
    monkeypatch.setattr(rerank_mod, "get_client", lambda p, c: _FakeClient([0]))
    out = await rerank_mod.rerank_chunks("q", cands, cfg)
    assert [c.id for c in out] == [0]      # all, no crash


@pytest.mark.asyncio
async def test_enrich_for_agent_wires_rerank_hook(tmp_path, monkeypatch):
    """ContextService builds the hook and passes candidate_k to storage."""
    from armance.service.context_service import ContextService
    from armance.storage import rag_index

    calls = {}

    def _fake_context_with_rag(root, query, k=8, rerank=None, candidate_k=None):
        calls["rerank_is_set"] = rerank is not None
        calls["candidate_k"] = candidate_k
        return "chunk-text"

    monkeypatch.setattr(rag_index, "context_with_rag", _fake_context_with_rag)
    cfg = Config(rerank_provider="custom-openai", rerank_model="m",
                 rerank_candidate_k=17, rerank_keep_n=3)
    svc = ContextService(tmp_path)
    out = await svc.enrich_for_agent("A", "base", "q", config=cfg)
    assert calls["rerank_is_set"] is True
    assert calls["candidate_k"] == 17
    assert "chunk-text" in out and "base" in out


@pytest.mark.asyncio
async def test_enrich_for_agent_no_rerank_config(tmp_path, monkeypatch):
    from armance.service.context_service import ContextService
    from armance.storage import rag_index

    calls = {}

    def _fake_context_with_rag(root, query, k=8, rerank=None, candidate_k=None):
        calls["rerank_is_set"] = rerank is not None
        return ""

    monkeypatch.setattr(rag_index, "context_with_rag", _fake_context_with_rag)
    svc = ContextService(tmp_path)
    out = await svc.enrich_for_agent("A", "base", "q", config=Config())
    assert calls["rerank_is_set"] is False
    assert out == "base"
