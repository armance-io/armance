# Vision

## One sentence

Armance is a **sovereign, contradictory, honest thinking partner** — a panel
of LLM agents that deliberate over *your* documents, on *your* machine, and
hand you a decision you can defend, not a deliverable.

"Many agents deliberating" is table stakes in 2026 — the multi-agent pattern is
commoditised. Armance's edge is not the number of agents but three deliberate
commitments to *not lying to you*:

1. **A contradictor by design.** Serge is a mandatory adversarial criticalist
   who runs on a **different model family** from the rest of the panel — so the
   room cannot quietly agree with itself. Anti-sycophancy is structural.
2. **Sources that don't lie.** Dated RAG plus a claims ledger: retrieved facts
   carry their provenance and date; conflicts are flagged, not smoothed over.
3. **A planetary cost it won't fabricate.** Every response reports its CO₂e and
   water footprint (EcoLogits, ISO 14044), computed offline — never an invented
   number, marked `~` when estimated.

And sovereign by doctrine: single-user, local-first, no SaaS. Your documents
never leave your machine — a choice, not a limitation.

## Why this distinction matters

The agent-tools market is converging on **makers**: copilots that produce
code, prose, slides, tickets. They optimise for throughput. They race to a
single answer.

The hardest minutes of strategic work are not throughput-limited. They are
**judgement-limited**. You need:

- a frame for an ambiguous problem,
- a disagreement between competent perspectives,
- a stress-test of the conclusion you are tempted by,
- a synthesis you can defend to a stakeholder.

Armance is built for those minutes. It does not write your code. It helps you
decide what code is worth writing.

## The panel — load-bearing roles, not a sales metaphor

The roles are an **engineering constraint**, not a pitch. Each agent has a
clear, narrow contract so the system can be reasoned about, tested, and later
parallelised across processes or machines:

- **The user** — owns the project, the constraints, the final call.
- **Armance** — host. Listens, frames, routes.
- **Malik** — recruiter. Casts panels whose personas *disagree along an
  axis meaningful to the role* (positivist vs revisionist; growth-hacker
  vs brand-purist; ship-fast vs rigorist).
- **Kim** — operator. Designs and runs the workflow. Owns process, not
  content.
- **Mona** — vice-president. Synthesises, names blind spots, recommends.
- **Serge** — mandatory adversarial criticalist. Red-teams every synthesis,
  running on a **deliberately different model family** from the rest of the
  panel so agreement can never be an artefact of a shared model's biases.

The value is not the head-count — it is that the room is *built to disagree*
and to keep the user in the chair.

## Five invariants

These are non-negotiable. Every feature is judged against them.

1. **Filesystem is the source of truth.** `.armance/` is the system. No DB
   for primary state. RAG sqlite is retrieval only.
2. **Markdown is the human–agent interface.** Agents, reports, contexts,
   conversations — all human-readable, diff-able, version-controllable.
3. **Disagreement is a feature.** Serge exists because consensus is a bug.
   Malik picks personas that argue. Kim runs panels in parallel.
4. **Sovereign, local-first.** Single-user by doctrine: a laptop install
   works without any server, and your documents never leave your machine.
   No SaaS, no cloud, no multi-tenant backend — a deliberate stance, not a
   missing feature. The web UI is a local transport (API + browser on your
   own host), never a hosted service.
5. **No autonomous side effects.** Armance never sends email, never opens a
   PR, never edits your code. It writes to `.armance/exports/` and `.armance/
   reports/`. The user remains the hands.

## What Armance is *not*

| Not | Why |
|---|---|
| A code copilot | Different problem. Makers exist; we pick decisions. |
| A chat app | Chat is the surface; the value is the panel + synthesis. |
| An autonomous agent | No external side effects. The user owns execution. |
| A SaaS / multi-tenant product | Sovereign by doctrine. Single-user, local-first; your data never leaves your machine. |
| A RAG search box | RAG is plumbing. Disagreement + synthesis is the product. |
| A workflow runner | YAML DAGs are the means. The point is the deliberation they orchestrate. |

## The web layer, framed

The web UI is a **local transport** — the same panel, in a browser served from
your own machine. It changes none of the invariants: single writer, files on
disk as the source of truth. Bound to the LAN, additional clients watch
read-only; only the first client may write. It is never a hosted, multi-tenant
service.

## The next frontier — local inference

Today your *data* is local, but *inference* still travels to a cloud API. The
direction — not yet shipped — is to make on-device inference (Ollama /
llama.cpp) a first-class provider, so a full Armance run can happen without a
single token leaving your machine. That is where sovereignty becomes complete.
It is a stated direction, not a delivered feature.
