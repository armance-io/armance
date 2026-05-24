# Web layer V2 — roadmap & user stories

> Status: **proposed**. Supersedes the thin P2.a stub in
> [`04_roadmap.md`](../../roadmap/04_roadmap.md) and the build sketch in
> [`web-layer.md`](web-layer.md).
> Author: brainstorm thread, 2026-05-23.

## Why the web layer is no longer optional

V1 ships a Textual TUI. It is functional and, for power users, fast. But
the product's stated audience is deliberately wide — students, retirees,
novelists, doctors, teachers, woodworkers — and the strategic analysis
flags the exact failure mode: a command-line surface *"rebuts non-technical
decision-makers"*. A TUI cannot be the only door.

The web layer is therefore promoted from a "nice parallel track" to a
**named phase with its own user stories**. It does not change the five
invariants of [`roadmap/01_vision.md`](../../roadmap/01_vision.md). In particular:

- **Local first stays local first.** V2 web is `localhost` (or trusted
  LAN). No hosted SaaS, no account, no upload of the user's documents to
  a third party. This is not a constraint we tolerate — it is a *product
  message*: **your data stays on your machine**. The landing page will
  say so out loud.
- **The web is a transport, not a rearchitecture.** The same firm
  (Armance / Malik / Kim / Mona / Serge), the same `.armance/` on disk,
  the same Markdown source of truth. The browser is a second window onto
  the same session — not a different product.
- A first-party hosted SaaS remains explicitly **out of scope**, deferred
  to a possible V3, and only if adoption pulls it. Priority order:
  adoption first, then the "your data, local" core message, then —
  maybe — hosting.

---

## Phase shape

```
P2.a  Web V2 — local browser UI         ← this document
  ├─ Epic A · Transport & session spine
  ├─ Epic B · The reading room (viewer)
  ├─ Epic C · The deliberation surface (chat + checkpoints)
  ├─ Epic D · The pipeline view (workflow runtime)
  ├─ Epic E · Onboarding in the browser
  └─ Epic F · Finish & feel (the "desire" layer)
```

Epics A→D are the functional core. E and F are what make the web layer
worth showing on the landing page. A→C are gating; D/E/F can land
incrementally behind them.

---

## Personas (referenced by the stories below)

- **Claire** — non-technical. Teacher, framing a class project. Has never
  opened a terminal. Judges the product in the first 30 seconds.
- **Driss** — semi-technical. Product manager. Comfortable with a browser
  app, not with a CLI. The strategic analysis' core target.
- **Guillaume** — power user / developer. Already lives in the TUI. Will
  use the web layer only if it doesn't slow him down.
- **A pair** — Driss + a colleague watching the same session on two
  machines on the same LAN. The multiplayer case.

---

## Epic A · Transport & session spine

The plumbing. Nothing user-visible ships from this epic alone, but
everything else depends on it.

### A1 — Serve the session over HTTP
*As Guillaume, I run one command and a browser tab shows my current
`.armance/` session, so that the web UI is never a separate install.*

- `armance web` (or `armance run --web`) starts a local server bound to
  `127.0.0.1` by default.
- Same `.armance/` directory, same config, same provider matrix. No new
  state store.
- TUI and web can both be attached to the same session; the filesystem
  remains the single source of truth.
- **Acceptance**: `armance web` in a project dir serves a page that
  reflects the real `.armance/` content. Closing the browser does not
  end the session.

### A2 — The `WebCheckpointHandler`
*As the system, when an agent needs input, I surface the same
checkpoint contract to the browser that the TUI already uses.*

- Implements the existing `CheckpointHandler` Protocol (`kind: text |
  select | confirm`) — the glue piece already scoped at ~40 LOC in
  `web-layer.md`.
- A checkpoint raised by any agent renders as a real form in the
  browser; the run blocks until the user answers, exactly as in the TUI.
- **Acceptance**: a `/model` preflight or a workflow-run confirm pauses
  the browser UI and resumes on submit. No divergence from TUI behaviour.

### A3 — Live updates without a refresh
*As Driss, I see the session evolve (new agent message, step status
change) without reloading the page.*

- Polling is acceptable for V2 (consistent with the TUI manifest-polling
  decision in [`workflow-runtime-ux.md`](workflow-runtime-ux.md)).
  No WebSocket/SSE requirement at V2.
- The page re-reads session state and the active manifest on a short
  interval while something is in progress.
- **Acceptance**: an agent reply or a step transition appears in the
  browser within ~1–2 s, no manual reload.

### A4 — LAN-trusted multiplayer (read-along)
*As a pair, my colleague opens the same session from their laptop on our
LAN and watches the deliberation in real time.*

- Optional bind to a LAN address, opt-in, off by default.
- V2 scope: the second viewer is **read-along** — they see the firm
  frame, cast, run; they do not drive. One driver, N watchers.
- Auth, RBAC, true multi-driver collaboration → V3.
- **Acceptance**: two browsers on the LAN show the same live session;
  only the driver's inputs take effect.

---

## Epic B · The reading room (viewer)

Read-only surfaces onto what `.armance/` already contains. Lowest risk,
highest "this is a real product" payoff. No `src/armance/` changes — pure
read endpoints + UI.

### B1 — Browse the library
*As Claire, I see which documents Armance has, which are indexed, and
which are loaded into the agents' context.*

- Renders the `/library` state: indexed slips (*feuillets*) vs the
  read set (full-text docs in context).
- Drop-zone affordance maps to "put a file in `.armance/docs/`" — but
  see B-note below.
- **Acceptance**: the library pane matches `/library status` exactly.

### B2 — Read a deliverable
*As Driss, I open a generated report / deliverable in the browser
instead of hunting for it in `.armance/exports/`.*

- Renders Markdown deliverables inline; offers the on-disk path and a
  download for pdf/docx/pptx exports.
- **Acceptance**: every `/deliverable` output is reachable from the UI
  within one click.

### B3 — Read past runs
*As Guillaume, I review a previous workflow run — its steps, durations,
token counts, and per-step output — from the browser.*

- Read endpoints mirror `runs.json` and the per-run `manifest.json`
  1:1 (the shape is already specified in
  [`workflow-runtime-ux.md`](workflow-runtime-ux.md), Story 3 web
  plan).
- **Acceptance**: `GET /workflows/<name>/runs` and
  `…/runs/<run_id>` return JSON identical to the on-disk manifest.

> **B-note — write affordances.** V2's question: can the browser *write*
> a file into `.armance/docs/` (upload), or only *view*? Recommended V2
> answer: allow upload into `.armance/docs/` because that is the one
> write a non-technical user genuinely cannot do otherwise (Claire will
> not `cp` a file). All other writes (save context, run workflow, export)
> stay agent-driven via chat. This keeps invariant #5 intact — the user,
> through the UI, is still "the hands"; the *agents* take no autonomous
> side effects.

---

## Epic C · The deliberation surface (chat + checkpoints)

The heart. This is where the firm metaphor becomes visible to someone
who will never read the spec.

### C1 — Talk to the firm
*As Claire, I type in plain language and the right agent answers, with
each agent visually distinct.*

- Chat transcript with clear agent identity (name, role, the portrait
  art). NL-first, exactly as the TUI; slash commands still available for
  power users.
- **Acceptance**: a full Armance → Malik → Kim journey is completable
  from the browser with zero slash commands.

### C2 — Answer a checkpoint as a form
*As Driss, when an agent asks me something, I get a clean form, not a
raw prompt.*

- Renders A2's checkpoint kinds as native controls: text field,
  select, confirm.
- **Acceptance**: each `kind` renders as the appropriate control; the
  run resumes on submit.

### C3 — See the recruitment, understand the why
*As Claire, when Malik proposes a panel, I see who he cast, and the axis
of disagreement each persona represents, before I approve.*

- The recruited panel renders as cards: persona, role, the axis they
  argue along (positivist vs revisionist, etc.).
- Approval is an explicit user action — this carries the manifesto:
  recruitment is transparent and pedagogical, never behind the user's
  back.
- **Acceptance**: no workflow starts until the user approves a panel
  they can actually read.

### C4 — Switch agent / model / effort visibly
*As Guillaume, I change agent, model, or reasoning effort from the UI as
fast as I do in the TUI.*

- `/switch`, `/model`, `/effort` equivalents as UI controls; preflights
  route through the `WebCheckpointHandler`.
- **Acceptance**: parity with the TUI's `/model` and `/effort` flows.

### C5 — Make the hypothesis ledger visible *(ties to the staff prompt
work)*
*As Driss, after an autonomous run, I see every assumption Mona made,
flagged and reviewable, so I can contest any of them.*

- When a workflow ran in autonomous mode, Mona's explicitly-traced
  hypotheses (see the staff-prompt adjustment) render as a distinct,
  reviewable list attached to the deliverable.
- **Acceptance**: every "Hypothèse (Mona)" entry from an autonomous run
  is listed in the UI, visually marked as an assumption, not a fact.

---

## Epic D · The pipeline view (workflow runtime)

The browser counterpart of Story 3 in
[`workflow-runtime-ux.md`](workflow-runtime-ux.md). The TUI sidebar
and the web view read the **same manifest**.

### D1 — Watch a workflow run live
*As Driss, while a workflow runs, I see each step move queued → working →
done, with live durations.*

- A CI/CD-style pipeline: step list, status, per-step duration and token
  count, agent spinners synced to `status == "working"`.
- Polling per A3.
- **Acceptance**: step transitions are visible without reload; durations
  reflect real `started_at` / `ended_at`.

### D2 — See the panel deliberate in parallel
*As Driss, when two specialists work independently, I see them running at
the same time, not one after the other.*

- The pipeline view reflects the parallel execution of Story 2
  (`asyncio.gather` per DAG level). Independent steps render as
  concurrent lanes.
- **Acceptance**: independent steps show overlapping run windows.

### D3 — Choose run depth before launch
*As Claire, before a workflow starts, I choose how deep it goes — a quick
deliberation or a full challenged analysis — in plain words.*

- Surfaces the existing interactive/autonomous and depth choice as a
  friendly pre-launch step ("a quick second opinion" vs "a thorough,
  challenged review"). Maps to
  `[EXECUTE:/workflow-run:<name>:<interactive|autonomous>]`.
- **Acceptance**: the depth/mode choice is presented in non-technical
  language and correctly drives the run mode.

---

## Epic E · Onboarding in the browser

`armance init` today is a terminal flow. Claire never gets there.

### E1 — First-run setup, no terminal
*As Claire, the first time I open the web UI on a fresh project, it walks
me through provider, default model, and budget — three questions, in the
browser.*

- Mirrors the slimmed `armance init` (3 questions — provider, default
  model, budget — per
  [`05_auto_embed_discovery.md`](05_auto_embed_discovery.md)).
- Writes `.armance/config.yaml` exactly as the CLI would.
- **Acceptance**: a fresh project is fully configured from the browser;
  the resulting `config.yaml` is identical to the CLI's.

### E2 — Embedding proposal in the browser
*As Claire, when I add my first document, Armance proposes how to index
it and I just say yes.*

- The auto-embed-discovery proposal flow (P2.b) rendered as a checkpoint
  in the browser instead of a terminal prompt.
- **Acceptance**: dropping a file triggers Armance's proposal in the UI;
  confirming writes the embedding config and indexes.

### E3 — The empty state teaches
*As Claire, a brand-new session shows me what Armance is for, not a blank
screen.*

- Empty state introduces the firm and suggests first moves ("describe a
  decision you're weighing", "drop a document you want examined").
- **Acceptance**: no dead-end blank screen on first open.

---

## Epic F · Finish & feel (the "desire" layer)

This epic is the difference between "a local web UI exists" and "people
want to open it". It is explicitly in scope because the product's
positioning is *desire*, not utility.

### F1 — The visual identity carries over
*As anyone, the web UI feels like the same world as the landing page and
the portraits — warm paper, restrained ink, violet used sparingly.*

- Shared palette and type with armance.io. The aged-paper cream, the
  restrained accent, the agent portraits as first-class UI elements.
- **Acceptance**: a screenshot of the web UI is indistinguishable in
  *feel* from the landing page.

### F2 — Calm motion
*As Driss, the interface breathes — agents appear, steps resolve — with
deliberate, unhurried motion, never flashy.*

- Reveal/transition timing tuned for "calm", honoured `prefers-reduced-
  motion`.
- **Acceptance**: motion is present, subtle, and fully disabled under
  `prefers-reduced-motion`.

### F3 — It is beautiful at rest
*As anyone, even an idle session — empty state, a finished run — looks
like a finished object.*

- No raw scaffolding visible; idle and completed states are designed,
  not default.
- **Acceptance**: every screen has a designed idle state.

---

## Cross-cutting acceptance (the whole phase)

- [ ] No change to the five invariants of `roadmap/01_vision.md`.
- [ ] No `src/armance/` rearchitecture — web lives under `web/`, the only
      glue is the `WebCheckpointHandler` and read endpoints.
- [ ] TUI and web can attach to the same `.armance/` session; filesystem
      stays the single source of truth.
- [ ] Binds to `127.0.0.1` by default; LAN exposure is explicit opt-in.
- [ ] No account, no telemetry, no document leaves the machine.
- [ ] Every agent-driven side effect still goes through an explicit
      `[EXECUTE:/…]` tag — the browser adds no implicit code path.

## Explicitly out of scope for V2 (→ V3)

- Hosted SaaS, accounts, auth, RBAC, multi-tenant indexing.
- True multi-driver collaboration (V2 multiplayer is read-along only).
- WebSocket/SSE push (polling is sufficient at V2).
- Autonomous external actions (email, PRs) — violates invariant #5,
  permanently out of scope, not just deferred.

## Suggested landing order

1. **Epic A** — spine. Nothing demoable, everything depends on it.
2. **Epic B** — the reading room. First demoable surface, zero core risk.
3. **Epic C** — the deliberation surface. The product becomes usable
   end-to-end in the browser.
4. **Epic D** — pipeline view. Builds on a stable C.
5. **Epic E** — onboarding. Can slot in once C is stable.
6. **Epic F** — finish & feel. Threaded through B→E, hardened last.

A→C is the minimum that lets a non-technical user complete a real
session in the browser. D/E/F are what make that session feel like the
manifesto.
