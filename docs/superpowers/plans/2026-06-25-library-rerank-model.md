# Library Rerank Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional rerank model to the library retrieval path so retrieval becomes two-stage (vector recall → rerank precision), routed only through already-configured providers via their native `/rerank` endpoint.

**Architecture:** Flat config fields (`rerank_provider`/`rerank_model`/`rerank_candidate_k`/`rerank_keep_n`) mirror the existing embedding config. A new `LLMClient.rerank` method (default raises; `OpenRouterClient` implements native `POST /rerank`, which also serves `custom-openai` since both register the same client class). The two RAG injection helpers gain a guarded two-stage branch that degrades to vector order on any failure. UX adds an optional rerank box below the embedding field in both `armance init` and the web setup wizard.

**Tech Stack:** Python 3.11+, pydantic `Config`, httpx, pytest + pytest-asyncio + respx, questionary (CLI), FastAPI (web setup), Next.js/React (web setup form).

## Global Constraints

- Python ≥ 3.11; `from __future__ import annotations` at top of every module.
- Type hints everywhere. `asyncio` for parallelism; no blocking I/O on the hot path.
- `logging` module; no `print` debug (CLI user-facing `print` in `cli.py` is fine — matches existing style).
- Python files ≤ 300 LOC; new files stay small.
- Layering: `client → transport → service → core`; lower layers never import upper.
- Rerank routed through configured providers only — no Voyage/Cohere/Jina-direct clients, no extra API keys, no `torch`.
- `OpenRouterClient` is registered for BOTH `openrouter` and `custom-openai` (`providers/__init__.py:30-31`) — implementing `rerank` once covers both.
- `claude-code` and `gemini` clients inherit the default `rerank` that raises `NotImplementedError`.
- Rerank is **active** iff both `rerank_provider` and `rerank_model` are non-empty.
- Conventional commits, signed off (`git commit -s`). DCO: `Signed-off-by: GrIc <guillaume@richard-pro.fr>`.
- Offline test suite only — no real network (respx for httpx, monkeypatch elsewhere).

---

### Task 1: Config fields + `rerank_active` helper + loader clamp

**Files:**
- Modify: `src/armance/config.py` (add fields to `Config`; add `rerank_active` helper; clamp in `load_config`)
- Test: `tests/test_config_rerank.py` (create)

**Interfaces:**
- Consumes: existing `Config` (pydantic `BaseModel`), `load_config()`.
- Produces:
  - `Config.rerank_provider: str = ""`, `Config.rerank_model: str = ""`,
    `Config.rerank_candidate_k: int = 20`, `Config.rerank_keep_n: int = 5`
  - `armance.config.rerank_active(cfg: Config) -> bool` — True iff both `rerank_provider` and `rerank_model` non-empty.
  - `load_config()` clamps: when active and `rerank_keep_n > rerank_candidate_k`, set `rerank_candidate_k = rerank_keep_n` and log a warning.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config_rerank.py
from __future__ import annotations

from armance.config import Config, rerank_active


def test_config_defaults_rerank_off():
    cfg = Config()
    assert cfg.rerank_provider == ""
    assert cfg.rerank_model == ""
    assert cfg.rerank_candidate_k == 20
    assert cfg.rerank_keep_n == 5
    assert rerank_active(cfg) is False


def test_rerank_active_requires_both():
    assert rerank_active(Config(rerank_provider="openrouter")) is False
    assert rerank_active(Config(rerank_model="x")) is False
    assert rerank_active(Config(rerank_provider="openrouter", rerank_model="x")) is True


def test_config_round_trip_with_rerank():
    cfg = Config(rerank_provider="openrouter", rerank_model="cohere/rerank-v3.5",
                 rerank_candidate_k=30, rerank_keep_n=4)
    dumped = cfg.model_dump()
    again = Config(**dumped)
    assert again.rerank_model == "cohere/rerank-v3.5"
    assert again.rerank_candidate_k == 30
    assert again.rerank_keep_n == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config_rerank.py -v`
Expected: FAIL — `ImportError: cannot import name 'rerank_active'` / attribute errors.

- [ ] **Step 3: Add fields + helper to `config.py`**

In `class Config(BaseModel)`, after the `embedding_model` line (`config.py:70`):

```python
    rerank_provider: str = ""
    rerank_model: str = ""
    rerank_candidate_k: int = 20
    rerank_keep_n: int = 5
```

After the `Config` class (module level), add:

```python
def rerank_active(cfg: Config) -> bool:
    """True iff a rerank provider AND model are both configured."""
    return bool(cfg.rerank_provider) and bool(cfg.rerank_model)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config_rerank.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Write the failing clamp test**

```python
# append to tests/test_config_rerank.py
import logging
from pathlib import Path

import yaml

from armance import paths
from armance.config import load_config


def test_loader_clamps_candidate_k_below_keep_n(tmp_path, monkeypatch, caplog):
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    cfg_file = cfg_dir / "config.yaml"
    cfg_file.write_text(yaml.safe_dump({
        "default_provider": "openrouter",
        "rerank_provider": "openrouter",
        "rerank_model": "cohere/rerank-v3.5",
        "rerank_candidate_k": 3,
        "rerank_keep_n": 5,
    }), encoding="utf-8")
    monkeypatch.setattr(paths, "global_config_path", lambda: cfg_file)
    monkeypatch.setattr(paths, "global_env_path", lambda: cfg_dir / ".env")
    with caplog.at_level(logging.WARNING):
        cfg = load_config()
    assert cfg.rerank_candidate_k == 5  # clamped up to keep_n
    assert any("rerank" in r.message.lower() for r in caplog.records)
```

- [ ] **Step 6: Run it to verify it fails**

Run: `uv run pytest tests/test_config_rerank.py::test_loader_clamps_candidate_k_below_keep_n -v`
Expected: FAIL — `assert 3 == 5`.

- [ ] **Step 7: Add the clamp in `load_config`**

In `config.py`, in `load_config()` after `cfg = Config(**raw)` (`config.py:113`) and before the default-provider guard:

```python
    if rerank_active(cfg) and cfg.rerank_keep_n > cfg.rerank_candidate_k:
        logger.warning(
            "rerank_keep_n (%d) > rerank_candidate_k (%d); clamping candidate_k up",
            cfg.rerank_keep_n, cfg.rerank_candidate_k,
        )
        cfg.rerank_candidate_k = cfg.rerank_keep_n
```

- [ ] **Step 8: Run the full file to verify all pass**

Run: `uv run pytest tests/test_config_rerank.py -v`
Expected: PASS (4 tests).

- [ ] **Step 9: Commit**

```bash
git add src/armance/config.py tests/test_config_rerank.py
git commit -s -m "feat(config): add optional rerank model fields + rerank_active helper"
```

---

### Task 2: `RerankHit` + `LLMClient.rerank` default + `OpenRouterClient.rerank`

**Files:**
- Modify: `src/armance/core/protocols/llm.py` (add `RerankHit`, default `rerank` method)
- Modify: `src/armance/providers/openrouter.py` (implement `rerank`)
- Test: `tests/test_rerank_provider.py` (create)

**Interfaces:**
- Consumes: `LLMClient` ABC, `OpenRouterClient` (`providers/openrouter.py:49`), existing `LLMHTTPError`, `_retry_after_seconds`, ledger logging helpers (`log_request`/`log_response`/`log_failure`/`get_ledger`).
- Produces:
  - `armance.core.protocols.llm.RerankHit` dataclass: `index: int`, `score: float`.
  - `LLMClient.rerank(self, query: str, documents: list[str], model: str, *, top_n: int | None = None) -> list[RerankHit]` — default raises `NotImplementedError`.
  - `OpenRouterClient.rerank(...)` — POST `/rerank`, returns `list[RerankHit]` sorted by score desc.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_rerank_provider.py
from __future__ import annotations

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
        import json
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_rerank_provider.py -v`
Expected: FAIL — `ImportError: cannot import name 'RerankHit'`.

- [ ] **Step 3: Add `RerankHit` + default `rerank` to `core/protocols/llm.py`**

After the `LLMResponse` dataclass (`llm.py:39`):

```python
@dataclass(slots=True)
class RerankHit:
    index: int    # original position in the documents list
    score: float  # relevance_score; higher = more relevant
```

Inside `class LLMClient(ABC)`, after `embed` (around `llm.py:57`):

```python
    async def rerank(
        self,
        query: str,
        documents: list[str],
        model: str,
        *,
        top_n: int | None = None,
    ) -> list["RerankHit"]:
        """Reorder documents by relevance. Default: provider has no rerank endpoint."""
        raise NotImplementedError(f"{type(self).__name__} has no rerank endpoint")
```

- [ ] **Step 4: Implement `OpenRouterClient.rerank` in `providers/openrouter.py`**

Add a method on `OpenRouterClient` (mirror the async `embed` at `openrouter.py:90`). Place it directly after `embed`:

```python
    async def rerank(
        self,
        query: str,
        documents: list[str],
        model: str,
        *,
        top_n: int | None = None,
    ) -> list[RerankHit]:
        """Native cross-encoder rerank via POST /rerank (Cohere-style).

        Serves both `openrouter` and `custom-openai` (same client class).
        Logs to the exchange log + ledger like embed."""
        from armance.service.llm_service import (
            get_ledger,
            log_failure,
            log_request,
            log_response,
        )

        log_request("rerank", model, [{"role": "user", "content": query[:200]}])
        url = self.base_url.rstrip("/") + "/rerank"
        headers = {"Content-Type": "application/json"}
        if self._provider.api_key:
            headers["Authorization"] = f"Bearer {self._provider.api_key}"
        body: dict[str, Any] = {"model": model, "query": query, "documents": documents}
        if top_n is not None:
            body["top_n"] = top_n
        try:
            response = await self._client.post(url, headers=headers, json=body)
            if response.status_code >= 400:
                raise LLMHTTPError(
                    f"openrouter rerank failed: {response.status_code} {response.text}",
                    status_code=response.status_code,
                    retry_after=_retry_after_seconds(response),
                )
            data = response.json()
            results = data.get("results") or []
            hits = [
                RerankHit(index=int(r["index"]), score=float(r.get("relevance_score", 0.0)))
                for r in results
            ]
            hits.sort(key=lambda h: h.score, reverse=True)
            usage = data.get("usage") or {}
            tokens_in = int(usage.get("total_tokens") or 0)
            log_response("rerank", model, LLMResponse(
                text=f"<rerank results={len(hits)}>",
                tokens_in=tokens_in, tokens_out=0,
                finish_reason="stop", cost_usd=None,
            ))
            try:
                get_ledger().record("rerank", tokens_in, 0, None)
            except Exception:
                pass
            return hits
        except Exception as exc:
            log_failure("rerank", model, exc, attempt=1, max_retries=1)
            raise
```

Ensure `RerankHit` is imported at the top of `openrouter.py` (add to the existing `from armance.core.protocols.llm import (...)` import). Confirm `Any` is imported (it is used; add `from typing import Any` if absent).

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_rerank_provider.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add src/armance/core/protocols/llm.py src/armance/providers/openrouter.py tests/test_rerank_provider.py
git commit -s -m "feat(providers): native /rerank on OpenRouterClient + LLMClient.rerank default"
```

---

### Task 3: Two-stage rerank in `_rag_inject.py` (async path)

**Files:**
- Modify: `src/armance/service/agents/_rag_inject.py` (add `_rerank_chunks`; branch in `inject_rag_section`)
- Test: `tests/test_rag_inject_rerank.py` (create)

**Interfaces:**
- Consumes: `rerank_active` (Task 1), `RagService.query` (`storage/rag_index.py:224`), `get_client` (`armance.service.llm_service`), `LLMClient.rerank` + `RerankHit` (Task 2), `Chunk`.
- Produces:
  - `armance.service.agents._rag_inject._rerank_chunks(query: str, candidates: list[Chunk], config) -> list[Chunk]` — returns top `keep_n` reordered; degrades to vector order on any error.
  - `inject_rag_section` two-stage branch when `rerank_active(config)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_rag_inject_rerank.py
from __future__ import annotations

import pytest

from armance.config import Config
from armance.core.protocols.llm import RerankHit
from armance.service.agents import _rag_inject


class _Chunk:
    def __init__(self, cid, text):
        self.id, self.text, self.source = cid, text, "doc"


class _FakeClient:
    def __init__(self, order): self._order = order
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
        async def rerank(self, *a, **k): raise RuntimeError("5xx")

    monkeypatch.setattr(_rag_inject, "get_client", lambda p, c: _Boom())
    import logging
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_rag_inject_rerank.py -v`
Expected: FAIL — `AttributeError: module ... has no attribute '_rerank_chunks'`.

- [ ] **Step 3: Add `_rerank_chunks` + import `get_client` at module level**

In `_rag_inject.py`, add near the top (module-level, so tests can monkeypatch `_rag_inject.get_client`):

```python
from armance.service.llm_service import get_client
```

Add the helper (after `inject_rag_section`, or before — keep file ≤ 250/300 LOC):

```python
async def _rerank_chunks(query: str, candidates: list, config) -> list:
    """Two-stage precision step: rerank candidates, keep top rerank_keep_n.

    Degrades to vector order on ANY failure (unsupported provider, HTTP,
    timeout, bad payload). Never raises."""
    keep_n = getattr(config, "rerank_keep_n", 5)
    try:
        client = get_client(config.rerank_provider, config)
        hits = await client.rerank(
            query, [c.text for c in candidates], config.rerank_model, top_n=keep_n,
        )
        ranked = [candidates[h.index] for h in hits if 0 <= h.index < len(candidates)]
        # any candidate the reranker omitted gets appended in vector order
        seen = {id(c) for c in ranked}
        ranked += [c for c in candidates if id(c) not in seen]
        return ranked[:keep_n]
    except Exception:
        logger.warning("rerank failed; falling back to vector order", exc_info=True)
        return candidates[:keep_n]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_rag_inject_rerank.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Wire the branch into `inject_rag_section`**

In `_rag_inject.py`, replace the single retrieval line (`_rag_inject.py:89`,
`chunks: list[Chunk] = await store.query(query, top_k=k)`) with:

```python
        from armance.config import rerank_active
        if rerank_active(config):
            candidates = await store.query(query, top_k=config.rerank_candidate_k)
            chunks = await _rerank_chunks(query, candidates, config)
        else:
            chunks = await store.query(query, top_k=k)
```

(`config` is the `inject_rag_section` param; it is non-None on the rerank path because `rerank_active` reads its attributes — guard already present is the embedding check above, which returns early when embedding unset, so the store exists.)

- [ ] **Step 6: Run the inject test module + existing rag inject tests**

Run: `uv run pytest tests/test_rag_inject_rerank.py tests/ -k "rag_inject or inject_rag" -v`
Expected: PASS; no regressions in existing inject tests.

- [ ] **Step 7: Commit**

```bash
git add src/armance/service/agents/_rag_inject.py tests/test_rag_inject_rerank.py
git commit -s -m "feat(rag): two-stage rerank branch in inject_rag_section (degrades to vector order)"
```

---

### Task 4: Two-stage rerank in `rag_index.context_with_rag` (sync path) + golden no-op test

**Files:**
- Modify: `src/armance/storage/rag_index.py` (`context_with_rag` two-stage branch)
- Test: `tests/test_context_with_rag_rerank.py` (create)

**Interfaces:**
- Consumes: `rerank_active` (Task 1), `_rerank_chunks` (Task 3 — import from `service.agents._rag_inject`), `RagService.query`.
- Note layering: `storage` is below `service`. `context_with_rag` already imports from `service`/elsewhere lazily inside the function body — do the rerank import lazily inside the function too, NOT at module top, to avoid a static `storage → service` import. (Check `scripts/check_invariants.sh` after.)
- Produces: `context_with_rag` returns reranked top-n when active; unchanged legacy `k` path when inactive.

- [ ] **Step 1: Write the failing golden + active tests**

```python
# tests/test_context_with_rag_rerank.py
from __future__ import annotations

from unittest.mock import patch

from armance.config import Config
from armance.storage import rag_index


class _Chunk:
    def __init__(self, cid, text):
        self.id, self.text, self.source, self.doc_anchor = cid, text, "doc", "1"


def test_context_with_rag_inactive_is_legacy(tmp_path, monkeypatch):
    # rerank inactive (default Config) → store.query called with the legacy k,
    # no rerank performed.
    calls = {}

    class _Store:
        def __init__(self, *a, **k): pass
        async def query(self, q, top_k):
            calls["top_k"] = top_k
            return [_Chunk(0, "t0"), _Chunk(1, "t1")]

    monkeypatch.setattr(rag_index, "RagService", _Store)
    monkeypatch.setattr(rag_index, "Chunk", _Chunk, raising=False)
    with patch("armance.storage.rag_status.has_indexed_chunks", return_value=True):
        out = rag_index.context_with_rag(tmp_path, "q", k=8, config=Config())
    assert calls["top_k"] == 8            # legacy k, not candidate_k
    assert "t0" in out and "t1" in out
```

Note: if `context_with_rag` does not currently accept a `config` kwarg, Step 3 adds it (default `None`). When `config is None`, behaviour is exactly legacy.

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_context_with_rag_rerank.py -v`
Expected: FAIL — `TypeError: context_with_rag() got an unexpected keyword argument 'config'` (or, if config already supported, assertion mismatch).

- [ ] **Step 3: Add `config` param + two-stage branch to `context_with_rag`**

In `rag_index.py`, change the signature (`rag_index.py:289`):

```python
def context_with_rag(armance_root: Path, query: str, k: int = 8, config=None) -> str:
```

Replace the retrieval inside `_run` (`rag_index.py:307-308`):

```python
        def _run() -> None:
            from armance.config import rerank_active
            if config is not None and rerank_active(config):
                cands = asyncio.run(store.query(query, top_k=config.rerank_candidate_k))
                from armance.service.agents._rag_inject import _rerank_chunks
                chunks.extend(asyncio.run(_rerank_chunks(query, cands, config)))
            else:
                chunks.extend(asyncio.run(store.query(query, top_k=k)))
```

- [ ] **Step 4: Run the golden test to verify it passes**

Run: `uv run pytest tests/test_context_with_rag_rerank.py -v`
Expected: PASS.

- [ ] **Step 5: Add the active-path test**

```python
# append to tests/test_context_with_rag_rerank.py
import pytest

from armance.core.protocols.llm import RerankHit


def test_context_with_rag_active_two_stage(tmp_path, monkeypatch):
    calls = {}

    class _Store:
        def __init__(self, *a, **k): pass
        async def query(self, q, top_k):
            calls["top_k"] = top_k
            return [_Chunk(i, f"t{i}") for i in range(5)]

    class _Client:
        async def rerank(self, q, docs, model, *, top_n=None):
            return [RerankHit(index=2, score=0.9), RerankHit(index=0, score=0.5)]

    monkeypatch.setattr(rag_index, "RagService", _Store)
    monkeypatch.setattr(rag_index, "Chunk", _Chunk, raising=False)
    from armance.service.agents import _rag_inject
    monkeypatch.setattr(_rag_inject, "get_client", lambda p, c: _Client())
    cfg = Config(rerank_provider="openrouter", rerank_model="m",
                 rerank_candidate_k=5, rerank_keep_n=2)
    with patch("armance.storage.rag_status.has_indexed_chunks", return_value=True):
        out = rag_index.context_with_rag(tmp_path, "q", k=8, config=cfg)
    assert calls["top_k"] == 5            # candidate_k, not legacy k
    assert "t2" in out and "t0" in out
    assert "t1" not in out                # truncated to keep_n=2
```

- [ ] **Step 6: Run both tests to verify they pass**

Run: `uv run pytest tests/test_context_with_rag_rerank.py -v`
Expected: PASS (2 tests).

- [ ] **Step 7: Pass `config` from callers of `context_with_rag`**

Find callers: `grep -rn "context_with_rag" src/armance`. The known caller is `service/context_service.py:323`. Pass the available `config`/`cfg` object as the new `config=` kwarg there (it is in scope in that method — verify and wire). If a caller has no config in scope, leave it (defaults to legacy).

Run: `grep -rn "context_with_rag(" src/armance`
For `context_service.py`, update the call to include `config=<the config var in scope>`.

- [ ] **Step 8: Run invariants + targeted tests**

Run: `bash scripts/check_invariants.sh`
Expected: PASS — no new `storage → service` static import (the `_rerank_chunks` import is lazy/in-function).

Run: `uv run pytest tests/test_context_with_rag_rerank.py tests/ -k "context_with_rag or context_service" -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/armance/storage/rag_index.py src/armance/service/context_service.py tests/test_context_with_rag_rerank.py
git commit -s -m "feat(rag): two-stage rerank in context_with_rag (lazy service import, golden no-op)"
```

---

### Task 5: CLI `armance init` — optional rerank box below embedding

**Files:**
- Modify: `src/armance/cli.py` (add `_ask_rerank`; call it after `_ask_embedding`; thread into config)
- Test: `tests/test_cli_init_rerank.py` (create)

**Interfaces:**
- Consumes: existing init flow (`_ask_embedding` at `cli.py:468`; `cfg_kwargs` build at `cli.py:492-499`), `questionary`.
- Produces:
  - `armance.cli._ask_rerank(embedding_provider: str, embedding_model: str, selected_providers: list[str], providers, language: str = "en") -> tuple[str, str]` — returns `(rerank_provider, rerank_model)` or `("", "")` if skipped/no embedding.
  - init wires `rerank_provider`/`rerank_model` into `cfg_kwargs` when set.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_init_rerank.py
from __future__ import annotations

from armance import cli


def test_ask_rerank_skips_when_no_embedding():
    # No embedding configured → rerank makes no sense → skip silently.
    assert cli._ask_rerank("", "", ["openrouter"], [], language="en") == ("", "")


def test_ask_rerank_blank_input_returns_empty(monkeypatch):
    class _Q:
        def ask(self): return ""
    monkeypatch.setattr(cli.questionary, "text", lambda *a, **k: _Q())
    out = cli._ask_rerank("openrouter", "emb-model", ["openrouter"], [], language="en")
    assert out == ("", "")


def test_ask_rerank_returns_provider_model(monkeypatch):
    class _Q:
        def ask(self): return "cohere/rerank-v3.5"
    monkeypatch.setattr(cli.questionary, "text", lambda *a, **k: _Q())
    out = cli._ask_rerank("openrouter", "emb-model", ["openrouter"], [], language="en")
    assert out == ("openrouter", "cohere/rerank-v3.5")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_init_rerank.py -v`
Expected: FAIL — `AttributeError: module 'armance.cli' has no attribute '_ask_rerank'`.

- [ ] **Step 3: Implement `_ask_rerank` in `cli.py`**

Add after `_ask_embedding` (`cli.py:212`). Free-text id (no rerank-discovery endpoint), provider defaults to the embedding provider, asked only when embedding is set:

```python
def _ask_rerank(
    embedding_provider: str,
    embedding_model: str,
    selected_providers: list[str],
    providers: list["ProviderConfig"],
    language: str = "en",
) -> tuple[str, str]:
    """Optional rerank model, asked right below the embedding model.

    Returns (rerank_provider, rerank_model). ("", "") when skipped or when
    no embedding is configured (rerank needs a recall stage to refine)."""
    if not embedding_provider or not embedding_model:
        return ("", "")
    print()
    print("  🔎  Optional: rerank model (improves library precision, fewer tokens).")
    print(f"      Leave blank to skip. Uses provider: {embedding_provider}")
    model_id = (questionary.text(
        f"Rerank model id for {embedding_provider} (blank = skip)"
    ).ask() or "").strip()
    if not model_id:
        print("  Rerank disabled.\n")
        return ("", "")
    print(f"\n  ✅  Rerank: {embedding_provider}/{model_id}\n")
    return (embedding_provider, model_id)
```

(NLS keys can be added later; inline English strings are acceptable for this optional power-user box and match the level of polish requested. If the maintainer prefers NLS, mirror `init.rag.*` under `init.rerank.*`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli_init_rerank.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Wire into the interactive init flow**

In `cli.py`, after `embedding_provider, embedding_model = _ask_embedding(...)` (`cli.py:468`):

```python
    rerank_provider, rerank_model = _ask_rerank(
        embedding_provider, embedding_model, selected, providers, language=language
    )
```

In the `cfg_kwargs` block (after `cli.py:499`):

```python
    if rerank_provider:
        cfg_kwargs["rerank_provider"] = rerank_provider
        cfg_kwargs["rerank_model"] = rerank_model
```

- [ ] **Step 6: Run the CLI test module + a smoke import**

Run: `uv run pytest tests/test_cli_init_rerank.py -v && uv run python -c "import armance.cli"`
Expected: PASS + clean import.

- [ ] **Step 7: Commit**

```bash
git add src/armance/cli.py tests/test_cli_init_rerank.py
git commit -s -m "feat(cli): optional rerank model box below embedding in armance init"
```

---

### Task 6: Web setup route — accept rerank fields

**Files:**
- Modify: `src/armance/web/backend/routes/setup.py` (`SetupInitIn` fields + `Config(...)` wiring)
- Test: `src/armance/web/backend/tests/test_setup_rerank.py` (create)

**Interfaces:**
- Consumes: `SetupInitIn` (`setup.py:24`), `setup_init` (`setup.py:55`), `Config` build (`setup.py:112`).
- Produces: `SetupInitIn.rerank_provider`/`rerank_model` optional; persisted into `Config`.

- [ ] **Step 1: Write the failing test**

```python
# src/armance/web/backend/tests/test_setup_rerank.py
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_setup_init_persists_rerank(client: AsyncClient, monkeypatch, tmp_path):
    captured = {}
    from armance.web.backend.routes import setup as setup_mod

    def _save(cfg):
        captured["rerank_provider"] = cfg.rerank_provider
        captured["rerank_model"] = cfg.rerank_model

    monkeypatch.setattr(setup_mod, "save_config", _save, raising=False)
    # Stub the rest of the persistence chain so the route returns 201.
    monkeypatch.setattr(setup_mod, "ensure_global_setup", lambda c: None, raising=False)
    monkeypatch.setattr(setup_mod, "write_env", lambda p: None, raising=False)
    monkeypatch.setattr(setup_mod, "ensure_data_tree", lambda r: None, raising=False)
    # config path self-check: point at a file that exists + parses
    # (use the existing conftest fixtures if they already isolate paths).

    body = {
        "provider": "openrouter", "api_key": "k", "model": "x",
        "embedding_provider": "openrouter", "embedding_model": "emb",
        "rerank_provider": "openrouter", "rerank_model": "cohere/rerank-v3.5",
    }
    resp = await client.post("/setup/init", json=body)
    assert resp.status_code in (201, 500)  # 500 only if path self-check unstubbed
    if resp.status_code == 201:
        assert captured["rerank_provider"] == "openrouter"
        assert captured["rerank_model"] == "cohere/rerank-v3.5"
```

Note: align stubbing with the existing `setup` test patterns in `src/armance/web/backend/tests/` (read a sibling setup test first to reuse its fixtures/monkeypatches so the path self-check at `setup.py:144-161` passes cleanly).

- [ ] **Step 2: Run it to verify it fails**

Run: `cd web && uv run pytest ../src/armance/web/backend/tests/test_setup_rerank.py -v`
Expected: FAIL — rerank fields ignored / `captured` empty (or 422 if `SetupInitIn` rejects unknown — it won't, pydantic ignores extra by default unless configured; the real failure is the Config not carrying them).

- [ ] **Step 3: Add fields to `SetupInitIn` + Config wiring**

In `setup.py`, in `class SetupInitIn`, after `embedding_model` (`setup.py:36`):

```python
    rerank_provider: Optional[str] = None
    rerank_model: Optional[str] = None
```

In the `Config(...)` constructor (`setup.py:112-120`), after `embedding_model=...`:

```python
        rerank_provider=body.rerank_provider or "",
        rerank_model=body.rerank_model or "",
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd web && uv run pytest ../src/armance/web/backend/tests/test_setup_rerank.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full web backend suite (no regressions)**

Run: `cd web && uv run pytest ../src/armance/web/backend/tests/`
Expected: PASS (existing 163 + new).

- [ ] **Step 6: Commit**

```bash
git add src/armance/web/backend/routes/setup.py src/armance/web/backend/tests/test_setup_rerank.py
git commit -s -m "feat(web): accept optional rerank_provider/rerank_model in setup route"
```

---

### Task 7: Web setup frontend — rerank box below embedding field

**Files:**
- Modify: the setup form component under `web/frontend/src/components/` that renders the embedding model input (locate via grep)
- Test: the matching `*.test.tsx` (vitest) for that component, or add one

**Interfaces:**
- Consumes: the existing embedding-model form field + the POST body sent to `/setup/init`.
- Produces: an optional rerank model input rendered directly below the embedding input; its value sent as `rerank_provider` (= embedding provider) + `rerank_model` in the init POST.

- [ ] **Step 1: Locate the embedding field in the frontend**

Run: `grep -rn "embedding_model\|embeddingModel\|embedding" web/frontend/src --include=*.tsx --include=*.ts`
Identify the setup component and the state/POST shape. Read it fully before editing.

- [ ] **Step 2: Write/extend the failing component test**

Add a vitest + @testing-library/react test asserting: a rerank input exists below the embedding input (select by `data-testid="setup-rerank-model"` — per the web-i18n-brittle-e2e memory, select by testid not label text), and typing a value includes `rerank_model` in the submitted payload. Mirror the existing embedding field's test for structure.

Run: `cd web/frontend && pnpm test -- <setup test file>`
Expected: FAIL — no `setup-rerank-model` element.

- [ ] **Step 3: Add the rerank input**

Below the embedding model field, add an optional text input with `data-testid="setup-rerank-model"`, label "Rerank model (optional)", bound to a `rerankModel` state value. On submit, when non-empty, include `rerank_provider: <embeddingProvider>` and `rerank_model: <rerankModel>` in the `/setup/init` POST body. When the embedding field is empty, disable/hide the rerank input (rerank needs a recall stage).

- [ ] **Step 4: Run the component test**

Run: `cd web/frontend && pnpm test -- <setup test file>`
Expected: PASS.

- [ ] **Step 5: Typecheck + lint**

Run: `cd web/frontend && pnpm typecheck && pnpm lint`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add web/frontend/src
git commit -s -m "feat(web): rerank model input below embedding field in setup form"
```

---

### Task 8: Full suite + invariants green; push branch

**Files:** none (verification + push)

- [ ] **Step 1: Core suite**

Run: `uv run pytest tests/`
Expected: PASS (existing ~1050 + new rerank tests).

- [ ] **Step 2: Invariants**

Run: `bash scripts/check_invariants.sh`
Expected: PASS (all checks; especially no `storage → service` / no `service → client` static import).

- [ ] **Step 3: Web backend suite**

Run: `cd web && uv run pytest ../src/armance/web/backend/tests/`
Expected: PASS.

- [ ] **Step 4: Frontend checks**

Run: `cd web/frontend && pnpm typecheck && pnpm lint && pnpm test`
Expected: PASS.

- [ ] **Step 5: Push the branch**

```bash
git push -u origin feat/library-rerank-model
```

---

### Task 9: Sync armance-strategie spec to shipped reality

**Files (in the sibling repo `../armance-strategie`):**
- Modify: `issues/features/library-rerank-model.md` (rewrite to match shipped design)
- Modify: `README.md` or `convergence.md` (add a spec-drift-prevention note)

- [ ] **Step 1: Rewrite the proposal**

Replace `armance-strategie/issues/features/library-rerank-model.md` so it describes the SHIPPED design: flat `Config` fields (`rerank_provider`/`rerank_model`/`rerank_candidate_k`/`rerank_keep_n`), `rerank_active` helper, `LLMClient.rerank` + native `POST /rerank` on `OpenRouterClient` (serving openrouter + custom-openai), two-stage branch in `_rag_inject.inject_rag_section` and `rag_index.context_with_rag` with degrade-to-vector-order, optional rerank box below embedding in init + web setup, ledger telemetry under agent `"rerank"`. Remove: `capability_models`/`CapabilityKey`/`is_capability_active`/`RerankSpec` discovery, Voyage/Cohere/Jina-direct providers, `[rerank-local]`/torch, the §4 corpus-threshold auto-discovery proposal. Mark status **shipped (feat/library-rerank-model, 2026-06-25)**.

- [ ] **Step 2: Add a drift-prevention note**

In `armance-strategie/README.md` (or `convergence.md`), add a short note: *feature specs in `issues/features/` must describe the actual codebase state; before drafting a spec that references shared infra (config shape, provider abstraction, tags), verify that infra exists in the public `armance` repo. Specs marking dependencies `✅` must point to merged code.*

- [ ] **Step 3: Commit (signed off) in the sibling repo**

```bash
cd ../armance-strategie
git add issues/features/library-rerank-model.md README.md
git commit -s -m "docs(rerank): sync spec to shipped design; add spec-drift-prevention note"
```

(Push of the sibling repo only if the maintainer asks — it is a separate private repo.)

---

## Notes for the implementer

- **Degrade, never block** is the rerank contract everywhere: any rerank failure (unsupported provider, HTTP, timeout, malformed payload) returns the vector-search order, logs a warning, raises nothing.
- **`custom-openai` is free**: it shares `OpenRouterClient`, so `rerank` works for it automatically if the user's endpoint exposes `/rerank`. No separate class.
- **Lazy imports for layering**: `storage/rag_index.py` must not statically import from `service`; keep the `_rerank_chunks` import inside the function body. Run `check_invariants.sh` to confirm.
- **Determinism in tests**: the rerank stub returns a fixed permutation; assert exact order.
