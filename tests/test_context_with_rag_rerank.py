from __future__ import annotations

from unittest.mock import patch

from armance.storage import rag_index


class _Chunk:
    def __init__(self, cid, text):
        self.id, self.text, self.source, self.doc_anchor = cid, text, "doc", "1"


def test_context_with_rag_no_hook_is_legacy(tmp_path, monkeypatch):
    calls = {}

    class _Store:
        def __init__(self, *a, **k):
            pass

        async def query(self, q, top_k):
            calls["top_k"] = top_k
            return [_Chunk(0, "t0"), _Chunk(1, "t1")]

    monkeypatch.setattr(rag_index, "RagService", _Store)
    with patch("armance.storage.rag_status.has_indexed_chunks", return_value=True):
        out = rag_index.context_with_rag(tmp_path, "q", k=8)
    assert calls["top_k"] == 8            # legacy k, not candidate_k
    assert "t0" in out and "t1" in out


def test_context_with_rag_hook_two_stage(tmp_path, monkeypatch):
    calls = {}

    class _Store:
        def __init__(self, *a, **k):
            pass

        async def query(self, q, top_k):
            calls["top_k"] = top_k
            return [_Chunk(i, f"t{i}") for i in range(5)]

    async def _hook(q, cands):
        calls["hook"] = len(cands)
        return [cands[2], cands[0]]       # precision cut owned by the hook

    monkeypatch.setattr(rag_index, "RagService", _Store)
    with patch("armance.storage.rag_status.has_indexed_chunks", return_value=True):
        out = rag_index.context_with_rag(
            tmp_path, "q", k=8, rerank=_hook, candidate_k=5
        )
    assert calls["top_k"] == 5            # widened to candidate_k
    assert calls["hook"] == 5
    assert "t2" in out and "t0" in out
    assert "t1" not in out                # hook kept only two


def test_context_with_rag_no_service_import():
    """Layer guard: storage must not import service (Rule 1).

    AST-based on purpose: import-linter (grimp) misses lazy imports inside
    nested closures, which is exactly how the violation slipped in once.
    """
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(rag_index))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("armance.service"), node.module
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("armance.service"), alias.name
