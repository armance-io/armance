# Journey — how Armance got here

A condensed trace. Not the changelog. Not the full sprint history. The
**inflection points** only.

## 2026-04 · Genesis

- Single-file CLI. One LLM call per "task". Markdown reports versioned by
  hand. Provider matrix decided early: OpenRouter (httpx + OpenAI-compatible)
  + claude-code SDK + Gemini + custom-OpenAI.
- The shape that survived everything else: **`.armance/` as the source of
  truth**, no DB, no auth, no server.

## 2026-04 → 2026-05 · From CLI to staff

- The four-meta-agent firm crystallised: **Armance / Malik / Kim / Mona**.
  Each one a real LLM agent with a distinct system prompt, not a hard-coded
  router.
- **Serge** was added as a mandatory adversarial criticalist, on a deliberately
  different model family from the rest of the team. Every recruitment Malik
  proposes includes Serge.
- Layered context (L0 / L1 / L2) replaced the early "one big prompt"
  approach. Specialists load L0 + L1[role] + L2[theme] at call time, with
  RAG enrichment via sqlite-vec.

## 2026-05 · The four-layer rewrite

- **`client / transport / service / core`** layering enforced. Lower
  layers import nothing from upper layers.
- `handlers.py` consolidated every slash-command dispatcher (grew to ~1.4k
  LOC — split is on the table, see [`04_roadmap.md`](04_roadmap.md)).
- TUI rewritten on Textual. Web stack parked on `wip/web-v0` and removed
  from the main line until P4.

## 2026-05 — recent · Engine maturation

- `service/workflow_engine.py` (rich engine with events, cross-family
  validation, Serge auto-invoke, consensus heuristic) coexists with the
  simpler `core/models/workflow.py` executor that production calls today.
  Unification is queued, not done.
- **Kim's `DesignWorkflowSkill`** went from literal template skeletons to
  **LLM-tailored steps** (S2 calls the configured LLM with brief + intent +
  team domains; falls back to literal on validation failure).
- **RAG injection** was wired into Armance, Malik, Kim — until this point
  only specialists could read user docs.
- **Language picker** added to `armance init`. A short voice overlay is
  appended to every system prompt so the entire staff (and recruited
  specialists) replies in the chosen language regardless of user input.
- `qa_live.py` reworked: dynamic OpenRouter free-model discovery (no more
  hard-coded model ids that go stale), plus RAG round-trip / language switch
  / workflow-tailoring differentiation tests. 35/35 logic checks pass on
  live free models today.

## What is *not* in this trace

- Sprint task IDs (`T-15d`, `R-10`, …) — they belonged to in-flight handoff
  notes and are gone with the cleanup.
- Per-feature commit lists — git log has them.
- Phase numbering from earlier specs — superseded by
  [`04_roadmap.md`](04_roadmap.md).

The reason for this file: keep a short, dated thread future agents can read
in 60 seconds before opening anything else.
