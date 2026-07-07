from __future__ import annotations

from unittest.mock import patch

import pytest

from armance.config import Config
from armance.service.agents import _rag_inject
from armance.storage import rag_index


class _Chunk:
    def __init__(self, cid, text):
        self.id, self.text, self.source = cid, text, "doc"


class _Store:
    calls: dict = {}

    def __init__(self, *a, **k):
        pass

    async def query(self, q, top_k):
        _Store.calls["top_k"] = top_k
        return [_Chunk(i, f"t{i}") for i in range(5)]


def _cfg(**kw) -> Config:
    return Config(
        embedding_provider="custom-openai", embedding_model="emb", **kw
    )


@pytest.mark.asyncio
async def test_inject_rag_section_two_stage(monkeypatch, tmp_path):
    """When rerank is configured, recall widens then rerank_chunks cuts."""
    _Store.calls = {}
    calls = {}
    monkeypatch.setattr(rag_index, "RagService", _Store)
    monkeypatch.setattr(_rag_inject, "get_client", lambda p, c: object())

    async def _fake_rerank(q, cands, cfg):
        calls["candidates"] = len(cands)
        return cands[:2]

    monkeypatch.setattr(_rag_inject, "rerank_chunks", _fake_rerank)
    cfg = _cfg(rerank_provider="custom-openai", rerank_model="m",
               rerank_candidate_k=5, rerank_keep_n=2)
    with patch("armance.storage.rag_status.has_indexed_chunks", return_value=True):
        out = await _rag_inject.inject_rag_section(tmp_path, "q", k=3, config=cfg)
    assert _Store.calls["top_k"] == 5     # candidate_k, not k
    assert calls["candidates"] == 5
    assert "t0" in out and "t1" in out
    assert "t2" not in out                # cut by the rerank step


@pytest.mark.asyncio
async def test_inject_rag_section_without_rerank_is_single_stage(monkeypatch, tmp_path):
    _Store.calls = {}
    monkeypatch.setattr(rag_index, "RagService", _Store)
    monkeypatch.setattr(_rag_inject, "get_client", lambda p, c: object())
    with patch("armance.storage.rag_status.has_indexed_chunks", return_value=True):
        out = await _rag_inject.inject_rag_section(tmp_path, "q", k=3, config=_cfg())
    assert _Store.calls["top_k"] == 3     # plain k
    assert "t0" in out
