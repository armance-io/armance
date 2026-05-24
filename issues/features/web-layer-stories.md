# Web layer V2 — overview & user stories

> Status: **proposed**.
> Companion to the build guide [`web-layer.md`](web-layer.md).
> Supersedes the thin P2.a stub in [`04_roadmap.md`](../../roadmap/04_roadmap.md).

## Why the web layer is no longer optional

V1 ships a Textual TUI. It is functional and, for power users, fast.
But the product's stated audience is deliberately wide — students,
retirees, novelists, doctors, teachers, woodworkers — and the strategic
analysis flags the exact failure mode: a command-line surface *« rebuts
non-technical decision-makers »*. A TUI cannot be the only door.

The web layer is therefore promoted from a *« nice parallel track »* to
a **named phase with its own user stories**. It does not change the
five invariants of [`roadmap/01_vision.md`](../../roadmap/01_vision.md):

- **Local first stays local first.** V2 web is `localhost` (or trusted
  LAN). No hosted SaaS, no account, no upload of the user's documents
  to a third party. This is a *product message*: **your data stays on
  your machine**. The landing page says so out loud.
- **The web is a transport, not a rearchitecture.** Same firm (Armance
  / Malik / Kim / Mona / Serge), same `.armance/` on disk, same
  Markdown source of truth. The browser is a second window onto the
  same session — not a different product.
- **A first-party hosted SaaS is explicitly out of scope**, deferred to
  a possible V3, and only if adoption pulls it. Priority order:
  adoption first, then the *« your data, local »* core message, then —
  maybe — hosting.

## Personas (used across all epic files)

- **Claire** — non-technical. Teacher, framing a class project. Has
  never opened a terminal. Judges the product in the first 30 seconds.
- **Driss** — semi-technical. Product manager. Comfortable with a
  browser app, not with a CLI. The strategic analysis' core target.
- **Guillaume** — power user / developer. Already lives in the TUI.
  Will use the web layer only if it doesn't slow him down.
- **A pair** — Driss + a colleague watching the same session on two
  machines on the same LAN. The multiplayer case (V2 = read-along).

## Epic files (one per epic, self-contained)

| Epic | File | Status | Depends on |
|---|---|---|---|
| **A** · Transport & session spine | [`web-a-spine.md`](web-a-spine.md) | ready | none |
| **B** · The reading room (viewer) | [`web-b-viewer.md`](web-b-viewer.md) | ready | A |
| **C** · The deliberation surface (chat + checkpoints) | [`web-c-deliberation.md`](web-c-deliberation.md) | ready | A |
| **D** · The pipeline view (workflow runtime) | [`web-d-pipeline.md`](web-d-pipeline.md) | partial | A + `workflow-runtime-ux` Story 2 + `workflow-live-pipeline` Phase 2 |
| **E** · Onboarding in the browser | [`web-e-onboarding.md`](web-e-onboarding.md) | partial | A ; E2 depends on `auto-embed-discovery` |
| **F** · Finish & feel (the "desire" layer) | [`web-f-finish.md`](web-f-finish.md) | ready (frontend-only) | none |

Each epic file is self-contained: user stories, backend dependency
table, file / module layout, TDD task list (test red → implement →
green), and acceptance criteria. A fresh agent can pick up a single
epic file and work it without reading the others.

## Suggested landing order

1. **Epic A** — spine. Nothing demoable, everything depends on it.
2. **Epic B** — the reading room. First demoable surface, zero core risk.
3. **Epic C** — the deliberation surface. The product becomes usable
   end-to-end in the browser.
4. **Epic D** — pipeline view. Builds on a stable C and on
   `workflow-live-pipeline` Phase 2.
5. **Epic E** — onboarding. Slots in once C is stable.
6. **Epic F** — finish & feel. Threaded through B → E, hardened last.

A → C is the minimum that lets a non-technical user complete a real
session in the browser. D / E / F are what make that session feel like
the manifesto.

## Cross-cutting acceptance (the whole phase)

- [ ] No change to the five invariants of `roadmap/01_vision.md`.
- [ ] No `src/armance/` rearchitecture — web lives under `web/`, the
      only glue is the `WebCheckpointHandler` and read endpoints. The
      few backend deltas this phase requires (manifest enrichment,
      event emissions for the spinner, recruit-proposed event) are
      scoped in their dedicated tickets:
      [`workflow-live-pipeline.md`](workflow-live-pipeline.md),
      [`auto-embed-discovery.md`](auto-embed-discovery.md).
- [ ] TUI and web can attach to the same `.armance/` session;
      filesystem stays the single source of truth.
- [ ] Binds to `127.0.0.1` by default; LAN exposure is explicit
      opt-in.
- [ ] No account, no telemetry, no document leaves the machine.
- [ ] Every agent-driven side effect still goes through an explicit
      `[EXECUTE:/…]` tag — the browser adds no implicit code path.

## Explicitly out of scope for V2 (→ V3)

- Hosted SaaS, accounts, auth, RBAC, multi-tenant indexing.
- True multi-driver collaboration (V2 multiplayer is read-along only).
- WebSocket / SSE push for true bidirectional pushes (polling is
  sufficient at V2 ; SSE is used inside the session but not for
  cross-tab coordination).
- Autonomous external actions (email, PRs) — violates invariant #5,
  permanently out of scope.
