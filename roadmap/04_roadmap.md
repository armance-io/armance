# Roadmap

Macro-phases. Coarse, not a sprint board.

## Where we are

**V1 (current).** Local Python CLI, Textual TUI, five built-in agents,
RAG over user docs, multi-provider Malik recruitment with reasoning-effort
gating, multilingual interface (EN/FR catalogues complete), `/library`
unified command for indexed-vs-read state, free-tier OpenRouter end-to-end
working. Pytest 889 pass / smoke 31/31 OK / ruff clean / 0 layer violations.

See [`03_assessment_2026-05-15.md`](03_assessment_2026-05-15.md) for the
detailed current-state audit.

---

## Open user-journey decisions (carry-over)

- **Armance → Kim → Malik flow.** Reorder so Kim decides the workflow,
  then asks Malik to fill the roles. If the user just wants to chat (no
  workflow), Armance routes directly to a specialist and skips Kim.
  Today: Armance → Malik → Kim, which produces role duplication between
  Malik's team and Kim's design. Partial mitigation already shipped:
  Kim is now instructed to **reuse the Malik roster** and emit
  `@Malik, recrute …` if a missing skill is needed; the dispatcher
  forwards the request. Full reorder still pending.
- **Agent-to-agent forwarding.** Implemented as a string interception
  (`@<MetaAgent>, <request>` at the start of an agent line). Should
  become a first-class `[FORWARD:@<agent>]` tag with a defined contract.

## Phase P1 — Engine cleanup (~1 day remaining)

Six of the seven P1 items landed in cycle 2026-05-15-b. Only P1.1
(workflow engine unification) remains, and it is now the *only* thing
gating the V2 web port.

### P1.1 · Workflow engine unification — ✅ DONE

One engine: `core.models.workflow.execute_workflow`. Optional
`pre_run_hook` / `post_run_hook` callables let handlers wire
`service.workflow_hooks.{validate_cross_family, check_consensus_and_maybe_invoke_serge}`.
The rich `WorkflowEngine` was **deleted as dead code** along with
`OperatorAgentService` — net −4056 LOC. No layer violations,
zero duplicate schemas.

### P1.2 · `handlers.py` split — ✅ DONE (foundation)

`handlers.py` went from 1724 → ~1100 LOC. Domain handlers extracted to
`service/library_ops.py`, `save_ops.py`, `role_ops.py`, `task_ops.py`,
`mona_ops.py`. The three coordination chat shells (Armance / Malik /
Kim) stay in handlers.py — they couple to RAG injection + provider
catalogue and would not benefit from further split.

### P1.3 · Remove the `rag_service.py` shim — ✅ DONE (file was already deleted, kept the audit only to confirm)

### P1.4 · No-questionary in `service/handlers` — ✅ DONE

`/model`, `/effort`, `/workflow run` preflight now route through
`ctx.checkpoint_handler`. `CheckpointHandler` gained `kind: text | select
| confirm` so the same Protocol drives the TUI and (later) the web.

### P1.5 · DesignWorkflowSkill LLM-tailored steps — ✅ DONE

Schema-validated via `Workflow.model_validate`; falls back to the
literal template on validation failure.

### P1.6 · Prompt diet Kim / Mona / Serge — ✅ DONE

197 → 137 LOC across the three remaining system agents (Armance + Malik
were trimmed in the previous cycle).

### P1.7 · qa_live coverage gaps — ✅ DONE (J + K + N added)

J is end-to-end. K asserts bytes on disk for md + docx (PDF + PPTX
depend on WeasyPrint / python-pptx being installed). N is signal-only
until P1.1 wires the rich engine into the user workflow path.

---

## Phase P2 — Web layer + Onboarding polish (parallel tracks)

Two independent tracks, can land in any order:

### P2.a — Web layer

See [`WEB_NEXT.md`](../WEB_NEXT.md) — single-file build guide. Eight
endpoints, ~1.4k LOC under `web/`, no `src/armance/` changes expected.
The `WebCheckpointHandler` is the only piece of glue (~40 LOC); the rest
is wiring.

### P2.b — Auto-discovered embedding model

See [`05_auto_embed_discovery.md`](05_auto_embed_discovery.md). Removes
the embedding question from `armance init` and lets Armance propose a
model when documents first appear, inferred from doc shape (text vs
multimodal) × budget. Builds on the live provider catalogue
(`armance.providers.discovery`) that landed 2026-05-17. ~6h estimate.

### P2.d — Workflow runtime UX

See [`06_workflow_runtime_ux.md`](06_workflow_runtime_ux.md). Three
stories on the run lifecycle: staff prompt scope (Mona/Serge stay
inside workflow scope, not project), parallel step execution, and a
CI/CD-style pipeline view in TUI + read endpoints for the future web
layer. Manifest schema and pre-run health-check already landed
2026-05-18. ~8h remaining.

### P2.c — Per-model parameter discovery

See [`05_auto_embed_discovery.md`](05_auto_embed_discovery.md)
(companion section). Extends `ModelSpec` with `context_window`,
`max_completion_tokens`, `supported_parameters`, `knowledge_cutoff`,
`is_moderated`, `supports_tools`. Malik picks better models per role,
Kim sizes workflows from real caps, LLM clients strip unsupported
fields before posting (no more silent 400s). ~4h after P2.b.

---

V2 stays single-user, single-machine (`localhost` or trusted LAN).
Auth, RBAC, multi-tenant indexing live in V3.

---

## Phase P3 — Industrial interop (V3, exploratory)

The standards that did not exist when Armance started have stabilised. We
adopt their **interfaces**, not their infrastructure.

- **MCP (Model Context Protocol)** — expose Armance skills as MCP tools.
  External agents (Claude Code, Cline, Roo) can drive a Armance session
  through their host process.
- **A2A (Agent-to-Agent)** — Malik's recruited specialists become
  addressable as A2A endpoints. A Armance workflow can include external
  agents as DAG nodes.
- **OpenTelemetry** — span every LLM call, every step, every checkpoint.
  The ledger gains a trace id.
- **OCI** — official container image. The web stack as a single
  `docker run` command.

No timeline. These land when a concrete user need pulls them.

---

## What is *not* on the roadmap

- A first-party hosted SaaS. Armance is a tool, not a platform.
- Agent marketplaces. Malik already casts personas; we do not need a store.
- Autonomous external actions (sending email, opening PRs). Violates
  invariant #5 of [`01_vision.md`](01_vision.md).
- LangChain / LlamaIndex adapters. We talk to providers directly. The
  abstraction tax is not worth it.

---

## How to read this with a fresh head

1. Read [`01_vision.md`](01_vision.md) — five minutes.
2. Read [`02_architecture.md`](02_architecture.md) — ten minutes.
3. Skim [`03_assessment_2026-05-15.md`](03_assessment_2026-05-15.md) for
   today's known gaps.
4. Pick the smallest item in **P1** that maps to your context.
5. Land it. Update this file if the macro-phase shape changes.
