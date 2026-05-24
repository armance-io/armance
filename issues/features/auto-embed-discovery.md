# Auto-discovered embedding model — proposal

> Status: **proposed, not started**. Sibling feature to the V2 web layer.
> See [`WEB_NEXT.md`](../WEB_NEXT.md) for the parallel web track.
> Author: Armance user-journey thread, 2026-05-17.

## Motivation

`armance init` currently asks the user for an embedding provider + model on
top of the chat provider + default model + budget. Most users have no idea
which embedding model fits their use case. Forcing the choice up-front:

- Adds friction to the first run (three questions where one would do).
- Locks in a decision the user can't yet evaluate — they haven't seen
  their own documents yet.
- Creates silent failure modes: a text embedding model picked at init
  cannot index the PDF the user drops in `.armance/docs/` six months later.
- Couples a permanent configuration choice to a transient `init` flow.

The fix: **let Armance discover documents, infer the right embedding shape,
propose a model, ask once, then persist the choice.**

## Goal

After this lands, `armance init` only asks:

1. `provider` (one or more)
2. `default_model`
3. `budget_effort`

That's it. No embedding question. The embedding configuration is created
on-demand by Armance when the user first drops documents in `.armance/docs/`.

## User journey (after the change)

```
$ armance init
  → provider? openrouter
  → default model? openai/gpt-4o-mini
  → budget effort? medium
  ✓ wrote .armance/config.yaml

$ # user drops report.pdf in .armance/docs/
$ armance run

Armance: « Salut. Je vois que tu as déposé `report.pdf` (texte, ~80 pages,
         pas encore indexé). Pour l'indexer dans la bibliothèque je propose
         `voyage-3-large` (multilingual, qualité élevée, budget modéré).
         OK ? Ou tu préfères un modèle plus économique / plus pointu ? »

User:   « OK »

Armance: « Configuré. J'indexe maintenant. »
        [EXECUTE:/library-configure-embedding]
        [EXECUTE:/library-index]
```

If the user drops an image-bearing PDF or a screenshot:

```
Armance: « Je vois que `slides.pdf` contient des diagrammes et des images.
         Tu veux que la bibliothèque les retrouve aussi quand tu poses
         des questions visuelles ? Si oui, je propose un embedding
         multimodal (`nvidia/llama-nemotron-embed-vl-1b-v2:free`).
         Sinon je traite le texte seul avec un embedding classique. »
```

## Detection rules (Armance-side, deterministic)

When Armance encounters at least one document in `.armance/docs/` AND
`config.embedding_model` is empty:

| Detected | Recommended shape       |
|---|---|
| Pure text (`.md`, `.txt`, `.pdf` with no images) | `text` |
| PDF with embedded images or diagrams             | `text` (default) OR `multimodal` (if user asks) |
| Image files (`.png`, `.jpg`, `.webp`)             | `multimodal` |
| Mixed corpus                                       | `multimodal` |

Detection lives in a new pure function `infer_embedding_shape(docs_dir)`
in `armance/storage/ingestion.py` (or sibling). No LLM call needed.

## Model proposal (per shape × budget)

The proposal is **derived live** from the configured provider's catalogue —
no hardcoded model strings in Python. The provider abstraction already
landed (`armance.providers.base.BaseProvider`, `discovery.discover_all`)
handles this; we just add a `list_embedding_models()` method.

| Shape       | Budget    | Selection heuristic |
|---|---|---|
| `text`      | free-first | First free embedding model in catalogue, prefer multilingual |
| `text`      | low        | Cheapest paid model with > 1024 dim |
| `text`      | medium     | Best quality / cost ratio (e.g. `voyage-3`) |
| `text`      | high       | Largest dim, strongest benchmarks (`voyage-3-large`, `text-embedding-3-large`) |
| `multimodal`| free-first | First free multimodal model (e.g. `nemotron-embed-vl`) |
| `multimodal`| low+       | Provider-specific best multimodal |

If the configured provider doesn't expose any embedding model in the
required shape, Armance says so explicitly and offers (a) switch to a
provider that does, (b) fall back to a degraded shape, (c) skip indexing.

## Implementation sketch (~6 hours)

### 1. Provider layer
- `armance/providers/base.py`: extend `BaseProvider` with
  `async def list_embedding_models(self) -> list[EmbeddingSpec]`.
  `EmbeddingSpec` = `id`, `provider`, `shape` (`text` | `multimodal`),
  `dim`, `context_window`, `tier`, `price_per_mtok`.
- `OpenRouterProvider.list_embedding_models()`: filter
  `/api/v1/models` to embedding modalities (already existing helper
  `_is_embedding_model` in `model_discovery.py`).
- `static_providers`: gemini exposes `text-embedding-004`,
  `gemini-embedding-001`; claude-code has no native embedding (return []).

### 2. Detection
- `armance/storage/embedding_inference.py`:
  - `infer_embedding_shape(docs_dir: Path) -> Literal["text", "multimodal"]`
  - `propose_embedding_model(shape, budget, catalogues) -> EmbeddingSpec | None`
- Pure functions, fully unit-testable, no LLM.

### 3. Armance prompt + tag
- `[EXECUTE:/library-configure-embedding:<provider>:<model>]` — new tag.
  Per-role allow-list: only Armance.
- Handler in `service/library_ops.py`: write `embedding_provider` +
  `embedding_model` into `config.yaml`, then proceed to `/library-index`
  if requested.
- Armance's system prompt gains a *Step A.5 — Embedding configuration*
  paragraph between *Pending docs* and *Project framing*: only fires when
  docs exist AND embedding is unconfigured.

### 4. CLI cleanup
- `armance/cli.py`: remove the embedding question from `armance init`.
  Migration: existing configs keep their `embedding_*` fields; missing
  fields trigger Armance's proposal flow.
- Update `ONBOARDING.md` + `README.md` to reflect the new minimal init.

### 5. Tests
- `tests/unit/storage/test_embedding_inference.py` — detect text vs
  multimodal from a temp `.armance/docs/` directory.
- `tests/integration/test_armance_embedding_proposal.py` — Armance sees a
  doc, proposes a model, user confirms, config gets written.

## Migration

Existing users keep their current config. The change is purely additive:

- If `embedding_provider` + `embedding_model` are set → use them, no
  proposal flow.
- If they are empty / missing → Armance proposes on first doc encounter.

No `armance migrate`. Zero breaking change.

## Non-goals

- Auto-switching embedding models mid-project. The first proposal is
  the permanent one until the user explicitly says *« change le modèle
  d'embedding »*.
- Reasoning about quality dimensions beyond shape × budget. The user can
  always ask Armance for a more pointed recommendation in NL.
- Quantitative quality benchmarks. We rely on tier (provider catalogue)
  + manual curation in the heuristic.

## Open questions

1. **Multilingual default?** Most Armance users are FR-speaking; should
   `text` × `medium` default to a multilingual model even if a
   French-tuned one would score higher on FR benchmarks? Probably yes —
   easier to defend, lower variance.
2. **Re-index on model change?** Today the codebase already rebuilds the
   sqlite-vec store when the dim changes. We keep that.
3. **`/library-configure-embedding` granularity:** per-document or
   global? Decision: **global** (KISS). Mixed corpora go multimodal.

## Acceptance criteria

- [ ] `armance init` no longer asks about embeddings (3 questions instead
      of 5).
- [ ] Dropping a `.txt` in `.armance/docs/` triggers Armance's proposal.
- [ ] Dropping a `.png` triggers a multimodal proposal.
- [ ] User can say *« plus économique »*, *« qualité maximum »*,
      *« je veux <model_id> »* and Armance reroutes accordingly.
- [ ] `config.yaml` ends up with valid `embedding_provider` +
      `embedding_model` fields after the proposal flow.
- [ ] No hardcoded model strings — every proposal is derived from
      `discover_all(cfg)`.

## Dependencies

- ✅ Provider abstraction (`armance.providers.base.BaseProvider`,
  `discovery.discover_all`) — landed 2026-05-17.
- ✅ Tag scrubbing per-role allow-list — landed earlier.
- ⏳ This document → implementation when the user gives the green light.

## Out of scope for V2

Lives alongside the V2 web layer (`WEB_NEXT.md`), not inside it. The web
layer reuses the same auto-discovery once it's wired.

---

# Companion track — Per-model parameter discovery (P2.c)

> Same author, same 2026-05-17 thread. Independent from embedding
> discovery; ships together because both rely on the same provider
> abstraction.

## Motivation

Right now Malik picks `provider:` + `model:` (+ optional
`reasoning:`). Everything else is implicit — `max_tokens`, `top_p`,
`top_k`, `temperature`, `tools`, `tool_choice`, context window — driven
by Armance defaults that work for some models and silently degrade for
others.

OpenRouter's `/api/v1/models` (and equivalent endpoints on Gemini /
Claude) expose the relevant metadata. We're currently ignoring it.

Example payload (OpenRouter, user-supplied 2026-05-17):

```json
{
  "id": "qwen/qwen3-coder:free",
  "context_length": 1048576,
  "architecture": { "modality": "text->text", "tokenizer": "Qwen3" },
  "pricing": { "prompt": "0", "completion": "0" },
  "top_provider": {
    "context_length": 262000,
    "max_completion_tokens": 262000,
    "is_moderated": false
  },
  "supported_parameters": [
    "frequency_penalty", "max_tokens", "presence_penalty",
    "stop", "temperature", "tool_choice", "tools",
    "top_k", "top_p"
  ],
  "knowledge_cutoff": "2025-06-30"
}
```

This gives us, per model:

- **Effective context window** — `top_provider.context_length` is the
  authoritative ceiling (often much smaller than `context_length`).
- **`max_completion_tokens`** — drives the cap on streamed output.
- **`supported_parameters`** — which knobs Armance can send safely. Today
  we always send `temperature` and `max_tokens`; some models reject
  unsupported fields with a 400.
- **`knowledge_cutoff`** — Kim / Mona can surface to the user when
  a workflow asks for "latest news" with a model that's stale by 18m.
- **`tools` / `tool_choice` presence** — gates whether Malik can pair
  this model with a workflow step that needs function-calling.
- **`is_moderated`** — flag for sensitive corpora (legal, medical).

## Goal

Extend the existing `ModelSpec` (just landed in
`armance.providers.base`) with these fields, then:

1. **Malik** picks better models for each role using
   `context_length` + `supported_parameters`.
2. **Kim / Cost estimator** reasons about
   `max_completion_tokens` when sizing a workflow run.
3. **LLM client wrappers** strip unsupported parameters before sending
   the request — no more silent 400s on free-tier models.

## Extended `ModelSpec`

```python
@dataclass(slots=True, frozen=True)
class ModelSpec:
    id: str
    provider: str
    pricing_in_per_mtok: float = 0.0
    pricing_out_per_mtok: float = 0.0
    context_window: int = 0             # max input tokens (authoritative)
    max_completion_tokens: int = 0      # max output tokens
    supports_reasoning: bool = False
    supports_vision: bool = False
    supports_tools: bool = False        # NEW
    supported_parameters: frozenset[str] = frozenset()  # NEW
    knowledge_cutoff: str | None = None # NEW (ISO date)
    is_moderated: bool = False          # NEW
    tier: Tier = "free"
    display_name: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
```

## Per-provider discovery

| Provider     | Endpoint | Fields recovered |
|---|---|---|
| `openrouter` | `GET /api/v1/models` | All of the above (already there) |
| `gemini`     | `GET /v1beta/models?key=…` | `inputTokenLimit`, `outputTokenLimit`, `supportedGenerationMethods`, `version` (acts as cutoff hint) |
| `claude-code`| static catalogue | Hand-curated; SDK doesn't expose machine-readable specs |
| `custom-openai` | `GET /v1/models` if implemented | Best-effort, fall back to defaults |

## Where it plugs in

### Malik — model selection
- Addon now lists, per model: `ctx=262k`, `tools=yes`, `cutoff=2025-06`.
- Heuristic: if user's workflow involves "latest news / current state",
  prefer models with recent `knowledge_cutoff`. If it involves
  tool-using specialists, prefer `supports_tools=True`.

### Kim — workflow sizing
- `cost.estimate_workflow()` reads `max_completion_tokens` per step's
  agent to refine its `total_tokens_out` estimate (currently a flat
  4000-token assumption).

### LLM client — parameter sanitisation
- `armance/providers/openrouter.py` (the client, not the discovery
  module) gains a `_strip_unsupported(payload, spec.supported_parameters)`
  call before `httpx.post`. Stops 400s when a free Qwen variant
  doesn't accept `presence_penalty`.

### Truncation upstream
- `specialist_runner` already truncates history; the cap can now be
  `min(spec.context_window, default_cap)` instead of a global constant.

## Implementation sketch (~4 hours, after embedding-discovery lands)

1. Extend `ModelSpec` dataclass — kw-only, all new fields default-safe
   so old call sites keep working.
2. Update `OpenRouterProvider._fetch()` to populate the new fields from
   the JSON (the example payload covers every field above).
3. Update `GeminiProvider.list_models()` to call `/v1beta/models`
   instead of returning the static catalogue (drop the hand-curated
   list once dynamic discovery works).
4. Add `_strip_unsupported(payload, supported_parameters)` in each LLM
   client, called from the shared base. Tag dropped fields in the
   `llm_exchanges.jsonl` ledger so we can audit.
5. Malik's `_build_models_context` surfaces the new fields in a compact
   form (`name (ctx=262k tools cutoff=2025-06)`).
6. `cost.py` uses `max_completion_tokens` when available.
7. Tests: roundtrip the example payload, assert all fields populated;
   verify `_strip_unsupported` removes `presence_penalty` when the
   model doesn't list it.

## Acceptance criteria

- [ ] `ModelSpec` carries `context_window`, `max_completion_tokens`,
      `supports_tools`, `supported_parameters`, `knowledge_cutoff`,
      `is_moderated`.
- [ ] OpenRouter discovery populates every new field from real API
      responses.
- [ ] Gemini discovery uses live `v1beta/models` instead of the static
      table.
- [ ] LLM clients refuse to send a payload key absent from
      `supported_parameters`.
- [ ] Malik surfaces the new metadata in her proposals (one extra line
      per model).
- [ ] Cost estimator uses `max_completion_tokens` when sizing a step.
- [ ] No hardcoded parameter lists anywhere; discovery drives everything.

## Dependencies

- ✅ Provider abstraction (this commit's foundation).
- ⏳ P2.b (embedding auto-discovery) for the matching shape on
  embedding models — same `EmbeddingSpec` extension.
- This document → implementation on green light.
