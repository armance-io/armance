# Local inference — Ollama / llama.cpp as a first-class provider

> Status: **PROPOSED** (2026-07-05). Strategic frontier item (P3).
> Doctrine anchor: [décision 1](../decisions.md).

## Why (strategic)

Armance is local-first on **data** (files, index, ledger never leave the
machine) but not on **inference**: every LLM call still travels to a cloud
API (OpenRouter, Gemini, Claude). In the 2026 sovereignty landscape this is
the last open flank — a hard local-first user rightly says "my prompts still
go to a third party."

Local inference closes it: the option to run the **entire** loop on the
user's own hardware. It is the highest-leverage P3 item because it converts
Armance's positioning from "local-first on files" to "sovereign end-to-end".

## What

Add a local-inference provider so Ollama (and, where practical, llama.cpp /
GGUF via an OpenAI-compatible server) sits **alongside** the existing cloud
providers in the same provider abstraction — same recruitment, same catalogue
discovery, same `call_with_ledger` chokepoint.

Not a replacement for cloud providers: a **peer**. The user chooses per
budget posture / per role. Cloud stays available; local becomes possible.

## Non-goals

- No bundled model weights, no model downloader UI in v1 (assume the user
  runs `ollama pull` themselves; discover what is already installed).
- No GPU orchestration, no quantisation tooling.
- No degradation of the cloud path — this is additive.

## Doctrine interactions (must hold)

- **Serge's cross-family rule survives.** Serge must run on a *different
  model family* from the team. Fully-local mode therefore needs at least two
  local families installed (e.g. a Llama-class team + a Qwen/Mistral-class
  critic), OR a hybrid where Serge stays cloud while the team is local. The
  feature must detect and warn when only one local family is available so the
  adversarial contract is never silently broken.
- **CO₂e / water ledger.** Local inference has a real (often *higher* per-token,
  lower-abstraction) energy cost. EcoLogits models cloud calls; local runs
  need an energy path (device draw × latency, or a flagged `~` estimate).
  The ledger must never fabricate — a local call with no model params falls
  back to the estimate tiers, flagged.
- **Provider catalogue.** Local models must flow through the live catalogue /
  param-discovery (P2.c) so Malik/Kim size workflows from real caps
  (context window, tool support) instead of assuming cloud defaults.

## Backend dependencies (verify against `armance@main` before drafting tasks)

- Provider abstraction shape (`armance.providers.*`) — where a new provider
  registers, how the catalogue enumerates models.
- `call_with_ledger` signature and where latency is captured.
- Reasoning-effort passthrough (local models mostly ignore it — strip
  unsupported params, like the P2.c "no silent 400s" rule).
- Budget-posture resolution (`optimised` / `free-first`) — add a local
  posture or a `prefer-local` flag.

## Open questions

- Ollama's OpenAI-compatible endpoint vs native API — which surface to bind?
- How to represent "local" in the model id namespace so recruitment and the
  catalogue don't collide with cloud ids.
- Serge fallback policy when only one local family exists: warn-and-continue,
  or hard-require cloud Serge?

## Acceptance criteria (draft — refine at COMPILE time)

- A user with Ollama running and ≥1 model can complete a full task and a full
  workflow with zero cloud LLM calls (verify: no outbound to provider hosts
  in the exchange log).
- Serge either runs cross-family locally or is explicitly reported as
  cloud-delegated; never silently same-family.
- Env-impact ledger records local calls (real or flagged `~`), never blank,
  never fabricated.
- Cloud path regression-free: existing provider tests still green.
