# Adaptive (tool-based) library retrieval — proposal

> Status: **proposed, not started** (drafted 2026-06-25). Companion to
> `library-rerank-model.md`: rerank improves
> *what* a retrieval returns; this doc decides *whether* to retrieve at
> all. Builds on the agentic tool-call machinery (specialists already use
> `[EXECUTE:…]` tags) and the per-model parameter discovery
> (`supports_tools`, [`auto-embed-discovery.md`](auto-embed-discovery.md)
> companion track). Independent and optional — when disabled, retrieval
> behaves exactly as today.

## Why

The user's report: *« j'ai l'impression que les requêtes auprès des
agents sont beaucoup plus lentes / qu'elles coûtent beaucoup de tokens au
fur et à mesure que j'indexe des docs. Idéalement il faudrait que l'agent
ne pioche dans la library QUE s'il en a besoin. »*

Diagnosis. The vector **search** is O(log n) — it does not get slower as
the corpus grows. What grows is the **injected context**: today the
library is consulted and its top-k chunks are stuffed into the prompt on
**every** turn, whether or not the question needs the firm's documents.
"Bonjour", "reformule ce paragraphe", "quelle heure de réunion" — all pay
the full retrieval-injection tax. As the corpus and the per-query top-k
grow, that tax grows with them.

### The misconception to kill up front

"Modern models already decide when to retrieve, so maybe we don't need
this" — **false framing.** Auto-inject vs. tool-based retrieval is an
**architecture choice in Armance's code**, not a model capability. If
Armance pastes chunks into the prompt every turn, the model never gets a
say — it just receives the text. The model can only *decide* to consult
the library if Armance **exposes the library as a tool** the model may
call. So the question isn't "does the model do it for us" (it can't,
unless we build the seam) — it's "do we want to build the seam, and is
the model good enough to use it well once we do."

On the second half: yes. The decision "call `search_library` or answer
directly" is a **single binary tool-call**, the easy case of agentic
tool use. Early-2026 small-tier models clear it comfortably — Gemini 3.5
Flash (MCP-Atlas agentic 83.6%), Claude Haiku 4.5 (best-in-tier
multi-step agentic + instruction following), GPT-5.5-class minis. They
struggle on *long multi-tool interdependent* sequences, which this is
not. So the model tier is not the constraint; the missing seam is.

### Why now (corpus crossed the threshold)

When the whole corpus fits a context window, retrieval is overhead you
can skip — just inject everything. The triggers for *needing* retrieval
gating: the corpus exceeds the window, per-request latency violates your
target, or long-context cost passes the RAG crossover. The user is past
that point ("des centaines et des centaines de pages"). They need
retrieval — but **adaptive** retrieval: fire it only when the model's own
knowledge / the conversation is insufficient. That is exactly *« pioche
QUE si besoin »*.

## What changes (the seam)

Two retrieval modes, selectable, with **auto-inject staying the default**
so nothing regresses:

| Mode | Behaviour | Cost shape |
|---|---|---|
| `auto` (today, default) | Library queried + top-k injected every turn | Every prompt pays retrieval, even trivial ones |
| `adaptive` (new, opt-in) | Library exposed as a `search_library(query)` tool. Agent calls it only when it judges the question needs the firm's documents. Trivial prompts → zero retrieval tokens | Baseline prompt pays nothing; +1 LLM round-trip only when the tool fires |

The trade-off is explicit and small: `adaptive` adds one extra model
round-trip *when* the tool is called (latency), in exchange for paying
**zero** retrieval/injection cost on every turn that doesn't need it
(usually most of them). For a large corpus consulted occasionally, that
is a large net win.

## Scope

| Item | Spec section |
|---|---|
| `retrieval_mode` config + the `auto`/`adaptive` switch | §1 |
| `search_library` exposed as an agent tool (provider-native function-calling) | §2 |
| Tool-use loop: detect call → run retrieval → feed result back | §3 |
| Model capability gate (`supports_tools`) + graceful fallback to `auto` | §4 |
| Optional lightweight gating heuristic for models without good tool-use | §5 |
| Telemetry: retrieval-fired rate, tokens saved | §6 |

## §1 — Config: `retrieval_mode`

```python
RetrievalMode = Literal["auto", "adaptive"]

@dataclass
class Config:
    ...
    retrieval_mode: RetrievalMode = "auto"   # default = today's behaviour
```

- `auto` → current pipeline: query library, inject top-k (or rerank
  top-n if `library-rerank-model.md` active)
  every turn. Unchanged.
- `adaptive` → library is **not** auto-injected; it is offered as a tool.

`adaptive` requires the chosen chat model to support tool calls
(`ModelSpec.supports_tools`, from the param-discovery companion track).
The loader validates this (§4).

### Tasks

```
A.1 — retrieval_mode config
  1. Add RetrievalMode literal + Config.retrieval_mode default "auto".
  2. Config round-trip test (absent field → "auto").
  3. Loader cross-check with supports_tools (see A.5).
```

## §2 — `search_library` as a tool

### Tool definition

A provider-native function/tool definition handed to the chat model on
every turn in `adaptive` mode:

```json
{
  "name": "search_library",
  "description": "Search the firm's indexed document library for passages relevant to a question. Call this ONLY when answering needs information from the firm's own documents (uploaded reports, notes, prior deliverables). Do NOT call it for general knowledge, greetings, rephrasing, or reasoning the conversation already contains.",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "A focused search query capturing the information need."
      }
    },
    "required": ["query"]
  }
}
```

The description **is the gating policy** — it tells the model when *not*
to call. Kept tight and example-free (small-model prompt hygiene, same
principle as the visual overlay in multimodal §5).

### Result feeding

When the model calls `search_library(query)`, Armance runs the existing
retrieval (with rerank if active), formats the surviving feuillets as the
tool result, and returns it to the model for a second completion. The
feuillet citations stay attached so the existing source-display path
(multimodal M.6) still works.

### Tasks

```
A.2 — search_library tool definition
  1. Build the tool spec; inject it into the model request only in
     adaptive mode.
  2. The retrieval invoked by the tool reuses query_library (so rerank
     composes automatically).
  3. Result formatter: feuillets -> tool-result text + retained citation
     ids.
  4. Tests: in auto mode, no tool offered; in adaptive mode, tool present
     in the request payload.
```

## §3 — Tool-use loop

### Flow

```
user turn
  │  adaptive mode → request includes search_library tool
  ▼
model completion
  ├─ no tool call  → answer streamed directly   (0 retrieval tokens) ✅
  └─ tool call: search_library(query)
        │  run query_library(query)  (+ rerank if active)
        │  format feuillets as tool result
        ▼
     second model completion with the tool result in context
        │  (model MAY call again — bounded by max_tool_iters, default 2)
        ▼
     answer streamed
```

- **Bounded iterations**: `max_tool_iters` (default 2) caps successive
  `search_library` calls so a confused small model can't loop. On cap
  hit, the loop stops and the model answers with what it has.
- **Multi-agent**: in workflows, the gate is **per agent**. Each
  specialist/Mona/Kim decides independently whether their step needs the
  library. A drafting step may never touch it; a fact-checking step
  always will.
- **Backoff**: the tool's retrieval respects the same rate-limit backoff
  as everything else (see
  [`provider-rate-limit-during-background-run.md`](provider-rate-limit-during-background-run.md)).

### Tasks

```
A.3 — Tool-use loop (TDD)
  1. Test (red): model returns no tool call → answer passes through, NO
     query_library invocation.
  2. Test (red): model returns search_library(q) → query_library(q)
     called once, result fed back, second completion produces the answer.
  3. Test (red): model calls the tool max_tool_iters+1 times → loop stops
     at the cap, answers anyway, warning logged.
  4. Implement the loop in the agent runner; both single-chat and
     workflow specialist paths.
  5. Test: citations from the tool result survive into the final reply.
```

## §4 — Capability gate + fallback

`adaptive` mode needs `supports_tools=True` on the chat model
(param-discovery companion track). Handling:

- **Loader-time**: if `retrieval_mode == "adaptive"` but the configured
  `capability_models["chat"]` model has `supports_tools=False`, the
  loader logs a clear warning and **falls back to `auto`** for the
  session (never silently breaks retrieval). It does not rewrite the
  config — the user's intent is preserved for when they switch to a
  tool-capable model.
- **Proposal hook**: when this happens, Armance can suggest switching to
  a tool-capable model (she already surfaces `supports_tools` per Malik's
  model context).

### Tasks

```
A.4 — Capability gate
  1. Loader: adaptive + supports_tools=False → warn + run as auto this
     session (config untouched).
  2. Test: adaptive requested, non-tool model → effective mode is auto,
     warning emitted.
  3. Test: adaptive requested, tool-capable model → effective mode is
     adaptive.

A.5 — Cross-checks
  1. Wire the loader cross-check from A.1.3.
  2. Armance surfaces "ce modèle ne supporte pas les outils — bascule
     sur un modèle compatible pour activer le mode adaptatif".
```

## §5 — Lightweight gating fallback (optional, no tool support)

For models that don't support native tools but where the user still
wants *« pioche que si besoin »*, a cheaper alternative to always-inject:
a **one-shot relevance gate** before retrieval. Armance asks the chat
model (or a tiny side model) a yes/no: *"does answering this turn require
the firm's documents?"* Only on "yes" does it run + inject retrieval.

This is the training-free adaptive-retrieval-gating idea (TARG-style):
cheap pre-check, skip retrieval when the model's own knowledge suffices.
Less elegant than native tool-use, but works on any model and still kills
the always-inject tax.

**Reco**: ship §2–§4 (native tool-use) first — it's the clean path for
the capable models the user actually runs (Gemini Flash, Haiku, GPT
minis). Treat §5 as a later fallback only if a meaningful share of users
run tool-less models. Logged here so the design space is recorded; **not**
in the first milestone.

### Tasks (deferred)

```
A.6 — One-shot gate (DEFERRED — only if tool-less models matter)
  1. gate_retrieval(turn, cfg) -> bool via a minimal yes/no completion.
  2. Inject only when True.
  3. Tests: trivial turn → False (no retrieval); doc-needing turn → True.
```

## §6 — Telemetry: prove the win

The whole point is fewer tokens on trivial turns. Make it measurable:

- Per session, log **retrieval-fired rate**: fraction of turns where
  `search_library` was actually called (adaptive) vs. 100% (auto).
- Log **estimated tokens saved**: `(turns_without_retrieval) ×
  (avg injected-context tokens in auto mode)`.
- Surface in the cost view so the user *sees* that adaptive mode cut
  their per-prompt cost — turning the original complaint into a visible
  improvement.

### Tasks

```
A.7 — Adaptive telemetry
  1. Counter: turns total vs. turns that fired search_library.
  2. Estimate tokens-saved from the skipped injections.
  3. Cost view shows retrieval-fired rate + tokens saved this session.
  4. Test: a scripted session of 5 trivial + 2 doc turns reports
     fired-rate 2/7 and a non-zero tokens-saved figure.
```

## Acceptance criteria

- [ ] `retrieval_mode` defaults to `auto`; absent config field → `auto`;
      `auto` behaviour is byte-for-byte today's (golden test).
- [ ] In `adaptive`, trivial turns produce **zero** `query_library`
      calls (the core requirement: *pioche que si besoin*).
- [ ] In `adaptive`, a doc-needing turn fires `search_library`, feeds the
      result back, and answers with citations intact.
- [ ] Tool-call loop is bounded by `max_tool_iters`; no infinite loops.
- [ ] `adaptive` on a non-tool model → falls back to `auto` with a clear
      warning; config is not mutated.
- [ ] Per-agent gating works in workflows (each step decides
      independently).
- [ ] Rerank (`library-rerank-model.md`)
      composes: when the tool fires, retrieval still reranks.
- [ ] Telemetry reports retrieval-fired rate and tokens saved.

## Open questions

1. **Default mode for new installs?** Keep `auto` as the global default
   (safe, no behaviour change), but should `armance init` *suggest*
   `adaptive` when the model is tool-capable? Reco: suggest, don't
   impose — a one-line note in init, default stays `auto`.
2. **`max_tool_iters` value?** 2 is conservative (one search, optional
   refine). Bump for research-heavy workflows? Reco: 2 default,
   per-workflow override possible later.
3. **Auto-promote to adaptive at the rerank threshold?** When the corpus
   crosses the rerank-suggestion threshold (300 feuillets,
   library-rerank §4), should Armance *also* propose flipping to
   `adaptive`? Reco: yes — same trigger, same conversation: "ta biblio
   grandit; je propose rerank + mode adaptatif". Bundle the two
   proposals.
4. **Tool description language (FR/ER)?** The gating quality depends on a
   crisp description. Keep it in the config `language`? Reco: yes, mirror
   the user language so the small model reasons in-language.

## Non-goals

- Multi-hop / iterative retrieval beyond `max_tool_iters` (HiPRAG-style
  deep agentic RAG) — out of scope, separate spec if ever.
- Replacing `auto` mode. `auto` stays — some users / corpora genuinely
  want everything injected every turn.
- Query rewriting / decomposition before search. The model writes the
  `query` argument; we don't pre-process it here.
- Streaming the retrieval mid-generation. The tool result arrives between
  completions, not inline.

## Dependencies

- ✅ Agentic `[EXECUTE:…]` tag + tool machinery (specialists already
  function-call).
- ⏳ `ModelSpec.supports_tools` + param-discovery (auto-embed-discovery
  companion track, P2.c) — needed for the §4 gate.
- ⤳ Composes with `library-rerank-model.md` (optional, independent).
- ⏳ This document → implementation on green light.
