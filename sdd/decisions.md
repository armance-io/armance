# Decisions

Numbered, never renumbered or deleted: a superseded entry shrinks to `n. Superseded by m.`, and git keeps its text.

## 1. Sovereign by doctrine: one user, one machine, no SaaS

2026-07-05. Armance is single-user, single-machine and local-first, by doctrine and not as a limit to lift later. The
web layer is a local UI (localhost or trusted LAN), never a deployment target. Auth, RBAC and multi-tenant indexing
are refused, not deferred. The strategic frontier is local inference, to close the last cloud dependency.

Evidence: multi-agent orchestration is commoditised in 2026 (CrewAI, AutoGen, LangGraph, and the coding hosts absorb
it natively); the agentic consulting segment belongs to large firms with six-figure deals. What is not commoditised
is the doctrine: Serge, dated RAG with a claims ledger, a footprint that is never made up. The market trend is
sovereignty (EU AI Act obligations from 2026-08-02, self-hosted inference for data residency).

Rejected: a hosted SaaS and the web V3/V4 ladder (GCP, shared projects), which would compete where Armance has no
edge; pitching Armance as a "multi-agent consulting firm".

## 2. Every extension strengthens an anti-lie mechanism or sovereignty

2026-07-06. No generic product surface. The directions kept: (a) a local memory of disagreements, the one proprietary
data a single-user tool may build up; (b) carbon governance as a constraint (budgets in money or CO2e that degrade
the run before they cut it), which first needs a global config level; (c) sovereign projects held by a network
allowlist (localhost, local inference, listed endpoints) rather than attested after the fact; (e) an exportable
reasoning receipt (who said what, dated sources, open disagreements, cost). (d), a contradictor chosen per decision
type, waits until (a) is stable.

Rejected: a "sovereignty seal" stating that nothing left the machine, which is a lie as long as a cloud LLM receives
the prompt.

## 3. Files are the state, Markdown the interface

Since the start. `.armance/` is the system: agents, contexts, conversations, runs and reports are Markdown or YAML,
readable, diffable, versionable. SQLite (sqlite-vec) serves retrieval only. The global directory holds machine-wide
config and secrets; a project folder holds only its data.

Rejected: a database for primary state, which nobody can read or diff and which ties the user to Armance.

## 4. Four layers, lower never imports upper

2026-05. `client -> transport -> service -> core`, enforced in CI by import-linter and `scripts/check_invariants.sh`.
The transport is shared DTOs and one event type, no façade.

Rejected: an abstract `Transport` class or RPC façade over the service layer (dead code once the web layer spoke
DTOs directly).

## 5. Side effects only through tags, never outside `.armance/`

Agents act by writing `[EXECUTE:/<command>]` tags, scrubbed against a per-role allowlist before interception. Armance
never sends mail, opens a PR or edits the user's code: it writes to `.armance/exports/` and `.armance/reports/`, and
the user remains the hands.

Rejected: matching the user's text to trigger actions (a hidden code path), and agents with external tools.

## 6. Serge is cross-family, and a family is a provider type

Serge runs on a model family different from the executors and from Mona; the check is hard where Serge is built. A
family is the provider type: two instances of one OpenAI-compatible endpoint are one family, `claude-code` is
Anthropic. The pre-run check only warns, the workflow staying the user's choice.

Rejected: counting provider names (two providers can serve one family); blocking a single-family workflow before it
runs.

## 7. One workflow engine, a pure function over a static DAG

2026-05-15. `execute_workflow` runs a YAML DAG with hooks injected by the caller. The stateful `WorkflowEngine` was
deleted with `OperatorAgentService` (about 4,000 lines). The Creuset (2026-07) unrolls its revision statically,
guarded by `run_if`, so every run stays checkable at parse time and replayable.

Rejected: two engines side by side; a dynamic revision loop; a template engine (double braces are enough).

## 8. A provider is a type plus a named instance

2026-07 (v0.4.1). `type:label` (`custom-openai:lab`) gives each endpoint its own config, key variable
(`CUSTOM_OPENAI_LAB_API_KEY`) and optional model allowlist, unioned with discovery. A project may add instances and
extend allowlists, never set a key.

Rejected: one endpoint per provider type, with the key derived from the type name.

## 9. Library freshness: replace, date, signal

2026-06-21. No version control of documents: an update archives the old file and indexes the new one, a document may
carry a date, every injected chunk names its source and date, and agents prefer the most recent source and flag
conflicts through the claims ledger. Not built yet: `sdd/issues/rag-versioning-temporality.md`.

Rejected: a full version lineage with as-of queries and a catalogue database, dropped rather than deferred.

## 10. Domain presets are pure data

2026-07-17. A preset pack only drops workflows and library documents where existing mechanisms read them; each pack
ships a replayable bench judged blind by another model family.

Rejected: domain branches in the engine (`if domain == ...`), which would fork the product per domain.

## 11. One model registry

2026-07. One source per model (provider type, family, effort tier, environmental factors, context
window, update date) read by discovery fallbacks, effort ordering, `model_family` and the footprint. Data versioned
in the repo; live discovery completes it, never the reverse. Not built yet: `sdd/issues/model-registry.md`.

Rejected: three systems that each must learn a new model (catalogue, family resolution, footprint factors), which
diverged in practice (a model missing from one provider, footprints estimated on a generic model).

## 12. Intent lives in this repo, next to the code

2026-11-05. The private strategy repo (intent, contracts, issues, decisions) is folded into `sdd/`, anonymized, so
that a change and its intent travel in the same commit, as SDD-Fabrik checks.

Evidence: with intent in a separate repo, an audit was the only defence against drift, and it lagged: the July audit
still listed as open a health gate fixed in PR #27.

Rejected: keeping the detached private repo; importing its git history, which holds names in clear.
