from __future__ import annotations

from unittest.mock import patch

from armance.config import Config
from armance.core.protocols.llm import RerankHit
from armance.storage import rag_index


class _Chunk:
    def __init__(self, cid, text):
        self.id, self.text, self.source, self.doc_anchor = cid, text, "doc", "1"


def test_context_with_rag_inactive_is_legacy(tmp_path, monkeypatch):
    calls = {}

    class _Store:
        def __init__(self, *a, **k):
            pass

        async def query(self, q, top_k):
            calls["top_k"] = top_k
            return [_Chunk(0, "t0"), _Chunk(1, "t1")]

    monkeypatch.setattr(rag_index, "RagService", _Store)
    with patch("armance.storage.rag_status.has_indexed_chunks", return_value=True):
        out = rag_index.context_with_rag(tmp_path, "q", k=8, config=Config())
    assert calls["top_k"] == 8            # legacy k, not candidate_k
    assert "t0" in out and "t1" in out


def test_context_with_rag_active_two_stage(tmp_path, monkeypatch):
    calls = {}

    class _Store:
        def __init__(self, *a, **k):
            pass

        async def query(self, q, top_k):
            calls["top_k"] = top_k
            return [_Chunk(i, f"t{i}") for i in range(5)]

    class _Client:
        async def rerank(self, q, docs, model, *, top_n=None):
            return [RerankHit(index=2, score=0.9), RerankHit(index=0, score=0.5)]

    monkeypatch.setattr(rag_index, "RagService", _Store)
    from armance.service.agents import _rag_inject
    monkeypatch.setattr(_rag_inject, "get_client", lambda p, c: _Client())
    cfg = Config(rerank_provider="openrouter", rerank_model="m",
                 rerank_candidate_k=5, rerank_keep_n=2)
    with patch("armance.storage.rag_status.has_indexed_chunks", return_value=True):
        out = rag_index.context_with_rag(tmp_path, "q", k=8, config=cfg)
    assert calls["top_k"] == 5            # candidate_k, not legacy k
    assert "t2" in out and "t0" in out
    assert "t1" not in out                # truncated to keep_n=2
