# Product

Armance is a sovereign, contradictory, honest thinking partner: a panel of LLM agents that deliberate over your
documents, on your machine, and hand you a decision you can defend, not a deliverable to ship.

## For whom

People who must make a call on their own material and answer for it: a founder weighing an investment, a small team
choosing between two plans, an author working on a manuscript, a craftsman checking a brief against norms. They
need a frame for an ambiguous problem, a disagreement between competent views, a stress test of the conclusion they
lean to, and a synthesis they can defend to a stakeholder. Those minutes are limited by judgement, not by
throughput. Armance does not write the code or the slides; it helps decide what is worth writing.

## Why it is different

Many agents deliberating is table stakes in 2026. The edge is three commitments to not lie to the user:

1. A contradictor by design. Serge is a mandatory critic running on a different model family from the rest of the
   panel, so the room cannot quietly agree with itself.
2. Sources that do not lie. Dated RAG and a claims ledger: a retrieved fact carries its source and date, a conflict is
   flagged, not smoothed over.
3. A footprint it will not make up. Every answer reports its CO2e and water (EcoLogits, ISO 14044), computed offline,
   bounded when data is missing and marked `~` when estimated.

And sovereign by doctrine: one user, local-first, no SaaS ([decision 1](decisions.md)).

## The panel

The roles are an engineering constraint, not a sales metaphor: each agent has a narrow contract, so the system can be
reasoned about and tested.

- The user owns the project, the constraints and the final call.
- Armance hosts: listens, frames, routes.
- Malik recruits panels whose personas disagree along an axis that matters for the role (ship fast vs rigorist,
  growth vs brand).
- Kim designs and runs the workflow: owns the process, not the content.
- Mona synthesises, names blind spots, recommends.
- Serge red-teams every synthesis, on another model family.

## Invariants

Every feature is judged against them.

1. Files are the source of truth: `.armance/` is the system ([decision 3](decisions.md)).
2. Markdown is the human-agent interface: agents, reports, contexts and conversations stay readable and diffable.
3. Disagreement is a feature: consensus is a smell, Serge exists for it.
4. Sovereign, local-first: a laptop install works without a server, and documents never leave the machine. The web UI
   is a local transport, never a hosted service.
5. No autonomous side effects: Armance writes to `.armance/exports/` and `.armance/reports/`, the user remains the
   hands ([decision 5](decisions.md)).

## Success

A decision the user can defend, with its disagreements and sources in view. Each domain preset carries a bench that
replays real cases against a frontier reference, judged blind by another model family; a preset is better when its
bench says so, not when it feels so.

## Non-goals

- A code or content copilot: makers exist; Armance helps choose.
- A chat app: chat is the surface, the panel and its synthesis are the product.
- An autonomous agent: no email, no PR, no edit of the user's files.
- A SaaS or multi-tenant product, an agent marketplace, LangChain or LlamaIndex adapters (providers are called
  directly, the abstraction tax is not worth it).
- A RAG search box or a workflow runner: both are plumbing for the deliberation.

## Next frontier

Data is local, inference still travels to a cloud API. Local inference (Ollama, llama.cpp) as a first-class provider
would let a whole run happen without a token leaving the machine; Serge's cross-family rule still holds there. It is a
direction, not a delivered feature: [roadmap](roadmap.md).
