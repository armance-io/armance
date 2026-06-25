# Library rerank model — design

> Date: 2026-06-25. Branch: `feat/library-rerank-model`.
> Source proposal: `armance-strategie/issues/features/library-rerank-model.md`
> (rewritten to match this design — see §7).

## Goal

Add an **optional rerank model** to the library retrieval path. Define it
once at config (a provider from the already-configured set + a rerank
model id), use it everywhere the library is queried. When set, retrieval
becomes two-stage: retrieve **wide** by vector cosine (recall), then
**rerank** and keep a small **top-n** (precision). Result: more relevant
chunks, fewer injected tokens per prompt as the corpus grows.

When unset, retrieval is **byte-for-byte today's single-stage path** —
zero behaviour change, zero new cost.

## Reality check (why this deviates from the original proposal)

The original proposal (`library-rerank-model.md`) was written against a
`capability_models` capability system (`CapabilityKey`,
`is_capability_active`, `get_binding`, `RerankSpec` discovery,
`/library-configure-capability` tag) it described as already shipped via
sibling epics (multimodal, auto-embed-discovery). **None of that exists in
the codebase.** What exists:

- `Config` is **flat**: `embedding_provider` / `embedding_model` strings
  (`config.py`). No `capability_models` dict.
- `LLMClient` (`core/protocols/llm.py`) is the real provider abstraction:
  `complete` + `embed`. `BaseProvider` (`providers/base.py`) only carries
  `list_models()` for discovery.
- RAG retrieval = `RagService.query(text, top_k)` (`storage/rag_index.py`),
  injected via `service/agents/_rag_inject.py` and the
  `rag_index.context_with_rag` helper.
- Four providers only: `openrouter`, `claude-code`, `gemini`,
  `custom-openai`. No Voyage/Cohere/Jina direct clients, no extra keys.

So this design **adapts to the current code**: flat config fields, a
`rerank` method on `LLMClient`, a two-stage branch in the existing
injection helpers. No capability layer, no auto-discovery proposal, no
third-party-direct providers, no `torch`/local cross-encoder.

## Mechanism — native `/rerank`, configured providers only

OpenRouter exposes a native rerank endpoint
(`POST https://openrouter.ai/api/v1/rerank`, Cohere-style: `model`,
`query`, `documents`, optional `top_n` → `results[]` with `index` +
`relevance_score`). custom-openai endpoints that expose `/rerank` use the
same shape. This mirrors the existing `embed` → `/embeddings` call in
`providers/openrouter.py` exactly.

`claude-code` and `gemini` have no rerank endpoint → their `rerank()`
raises `NotImplementedError`. The two-stage path treats that like any
other rerank failure (degrade to vector order), and the config UX simply
lets the user point rerank at a provider that supports it.

```
query
  │ embed (existing path)
  ▼
vector search  →  top rerank_candidate_k   (cheap, recall stage)
  │
  │ POST /rerank (rerank_provider, rerank_model)
  ▼
results sorted by relevance_score  →  keep rerank_keep_n   (precision)
  │
  ▼
inject keep_n only
```

## §1 — Config (flat, mirrors embedding)

Add to `Config` (`config.py`):

```python
rerank_provider: str = ""        # "" → rerank OFF (default)
rerank_model: str = ""           # rerank model id on rerank_provider
rerank_candidate_k: int = 20     # vector-search width when rerank active
rerank_keep_n: int = 5           # survivors after rerank
```

Rerank is **active** iff both `rerank_provider` and `rerank_model` are
non-empty — same gate style as the embedding check in
`_rag_inject.inject_rag_section`. A small helper
`rerank_active(cfg) -> bool` centralises the check.

Loader validation: if active and `rerank_keep_n > rerank_candidate_k`,
log a warning and clamp `rerank_candidate_k = rerank_keep_n`.

## §2 — `LLMClient.rerank` + provider impls

Add to `core/protocols/llm.py`:

```python
@dataclass(slots=True)
class RerankHit:
    index: int      # original position in the documents list
    score: float    # relevance_score, higher = more relevant

class LLMClient(ABC):
    async def rerank(
        self, query: str, documents: list[str], model: str,
        *, top_n: int | None = None,
    ) -> list[RerankHit]:
        """Reorder documents by relevance. Default: not supported."""
        raise NotImplementedError(f"{type(self).__name__} has no rerank endpoint")
```

Default raises (so `claude-code` / `gemini` inherit "unsupported").

`OpenRouterClient.rerank` (`providers/openrouter.py`): POST `/rerank`
with `{model, query, documents, top_n}`, parse `results[]` into
`RerankHit(index, relevance_score)` sorted by score desc. Log to the
exchange log + global ledger under agent name `"rerank"`, mirroring
`embed`. Reuse the existing `LLMHTTPError` / retry-after machinery.

custom-openai uses the OpenAI-compatible client; if that is the
OpenRouter client variant pointed at a custom base_url, it inherits the
same `/rerank` POST. (Verify the custom-openai client wiring during
implementation; if it's a distinct class, add the same method.)

## §3 — Two-stage wiring

Both injection helpers gain a guarded branch.

`service/agents/_rag_inject.inject_rag_section`:

```python
if rerank_active(config):
    candidates = await store.query(query, top_k=config.rerank_candidate_k)
    chunks = await _rerank_chunks(query, candidates, config)  # → keep_n
else:
    chunks = await store.query(query, top_k=k)   # legacy, unchanged
```

`_rerank_chunks(query, candidates, cfg)`:
1. `client = get_client(cfg.rerank_provider, cfg)`
2. `hits = await client.rerank(query, [c.text for c in candidates], cfg.rerank_model, top_n=cfg.rerank_keep_n)`
3. return `[candidates[h.index] for h in hits][:cfg.rerank_keep_n]`
4. **on any exception** (NotImplementedError, HTTP, timeout, bad payload):
   log a warning, return `candidates[:cfg.rerank_keep_n]` (vector order).
   Never raises.

Same branch added to `rag_index.context_with_rag` (the sync helper) so
both meta-agent and specialist injection paths benefit. The sync helper
keeps its thread/`asyncio.run` wrapper.

Tiny corpus: if `len(candidates) < keep_n`, return all — no crash.

## §4 — Config UX (box below embedding, no new step)

The rerank model is entered **directly below the optional embedding model
field**, same UX pattern, not a new wizard step.

- Web setup (`web/backend/routes/setup.py` + frontend setup form): add an
  optional `rerank_provider` / `rerank_model` pair beneath the embedding
  inputs. Empty = rerank off.
- `armance init` (CLI): an optional prompt immediately after the embedding
  prompt; blank skips. Matches the embedding entry style (free-text or
  discovered-list — match whatever embedding does).

No corpus-threshold auto-discovery proposal (original §4 dropped).

## §5 — Telemetry

Each rerank call records to the existing exchange log + global ledger
under agent `"rerank"` (via the same `log_request`/`log_response`/
`get_ledger().record` calls `embed` uses). So rerank cost surfaces in the
TUI/web total like embedding cost — visible, never silent.

## Testing

- **Golden (red→green):** rerank inactive → `inject_rag_section` /
  `context_with_rag` return byte-for-byte the legacy single-stage result
  (`top_k`, cosine order); no `rerank()` call made.
- Active → vector search asked for `rerank_candidate_k`; `rerank()` called
  once with all candidate texts; result reordered + truncated to
  `rerank_keep_n` in the reranker's order. respx-mock the OpenRouter
  `/rerank` payload.
- Failure (rerank raises / 5xx / NotImplementedError) → fall back to
  vector order, `keep_n` items, warning logged, no exception propagated.
- Tiny corpus (candidates < keep_n) → return all, no crash.
- Config round-trips with and without rerank set; clamp test
  (`keep_n > candidate_k` → clamped).
- `OpenRouterClient.rerank` maps a sample `/rerank` response to the right
  `RerankHit` order (respx).

## §7 — Sync armance-strategie

After the feature lands, rewrite
`armance-strategie/issues/features/library-rerank-model.md` to match
shipped reality: flat config fields, native `/rerank` via configured
providers, `LLMClient.rerank`, two-stage injection, no `capability_models`,
no third-party-direct providers, no local cross-encoder, no auto-discovery.
Mark it shipped. Add a short process note (README/convergence) that specs
must track the codebase, so spec-vs-code drift like this doesn't recur.

## Acceptance criteria

- [ ] `rerank_provider`/`rerank_model` unset → retrieval is byte-for-byte
      the current single-stage path (golden test).
- [ ] Both set → retrieve-wide (`candidate_k`) → rerank → keep `keep_n`.
- [ ] Reranker failure (incl. unsupported provider) degrades to vector
      order, never raises.
- [ ] OpenRouter native `/rerank` works (respx-tested); custom-openai
      uses the same path.
- [ ] No third-party-direct providers, no extra API keys, no `torch`.
- [ ] Rerank model entered as an optional box below the embedding field in
      both web setup and `armance init`.
- [ ] Rerank cost visible in the ledger.
- [ ] `armance-strategie` spec rewritten to match shipped reality.

## Non-goals

- Capability_models layer / multimodal / auto-embed-discovery siblings.
- Corpus-threshold auto-discovery proposal (original §4).
- Local cross-encoder / `[rerank-local]` dependency group.
- Ranking by anything other than relevance (recency, authority, BM25
  fusion) — future, separate spec.
