# Vision

## One sentence

Armance is a **brain, not a maker** — a small firm of LLM agents that
deliberate over your documents and hand you a decision, not a deliverable.

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

## The firm metaphor — load-bearing

Armance models a tiny consulting firm:

- **CEO** — the user. Owns the project, the constraints, the final call.
- **Armance** — host. Listens, frames, routes.
- **Malik** — recruiter. Casts panels whose personas *disagree along an
  axis meaningful to the role* (positivist vs revisionist; growth-hacker
  vs brand-purist; ship-fast vs rigorist).
- **Kim** — operator. Designs and runs the workflow. Owns process, not
  content.
- **Mona** — vice-president. Synthesises, names blind spots, recommends.
- **Serge** — adversarial criticalist. Stress-tests every synthesis. Runs on
  a deliberately different model family from the rest of the team.

This is not flavour. It is the engineering constraint: each agent has a
**clear, narrow contract** so the system can be reasoned about, tested, and
later parallelised across processes or machines.

## Five invariants

These are non-negotiable. Every feature is judged against them.

1. **Filesystem is the source of truth.** `.armance/` is the system. No DB
   for primary state. RAG sqlite is retrieval only.
2. **Markdown is the human–agent interface.** Agents, reports, contexts,
   conversations — all human-readable, diff-able, version-controllable.
3. **Disagreement is a feature.** Serge exists because consensus is a bug.
   Malik picks personas that argue. Kim runs panels in parallel.
4. **Local first.** A single-user laptop install must work without any
   server. The web layer, when it lands, is a transport change — not a
   rearchitecture.
5. **No autonomous side effects.** Armance never sends email, never opens a
   PR, never edits your code. It writes to `.armance/exports/` and `.armance/
   reports/`. The user remains the hands.

## What Armance is *not*

| Not | Why |
|---|---|
| A code copilot | Different problem. Makers exist; we pick decisions. |
| A chat app | Chat is the surface; the value is the panel + synthesis. |
| An autonomous agent | No external side effects. The CEO owns execution. |
| A RAG search box | RAG is plumbing. Disagreement + synthesis is the product. |
| A workflow runner | YAML DAGs are the means. The point is the deliberation they orchestrate. |

## The web layer, framed

The forthcoming web UI is the **same
firm**, multiplayer, browser-accessible. It does not change the invariants.
A team can watch Armance frame the room, Malik cast the panel, Kim run the
workflow — in real time. The files written remain the source of truth.
