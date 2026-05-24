# Web Epic F · Finish & feel (the "desire" layer)

> Status: **frontend-only; can land incrementally alongside B / C / D /
> E**.
> Part of [`web-layer-stories.md`](web-layer-stories.md).

## Goal

The difference between *« a local web UI exists »* and *« people want
to open it »*. The product positioning is *desire*, not utility — and
the landing page (`armance.io`) sets the bar. The web UI must look and
feel like the same world.

## User stories covered

- **F1** — Visual identity carries over (palette, type, agent portraits
  as first-class UI elements).
- **F2** — Calm motion (subtle reveals; honours `prefers-reduced-motion`).
- **F3** — Beautiful at rest (every state is a finished object, never
  raw scaffolding).

## Backend dependencies

None. Pure frontend epic. The agent portraits live at `armance.io`'s
asset path and will be copied into `web/frontend/public/portraits/`.

## File / module layout

```
web/frontend/
  public/portraits/   armance.png + monogram placeholders for non-staff
  app/
    globals.css       palette tokens + type scale (mirrors armance.io)
    layout.tsx        shell — header, side rails, footer fleurons
    components/
      Fleuron.tsx     the ❦ used as section divider
      AgentPortrait.tsx
      EmptyState/*    designed idle states per pane
```

## TDD task list

### Task F.1 — Palette tokens + type scale
1. Frontend test (red — Storybook visual regression): the `<body>` of
   any page renders with the warm-cream background `#f4ede0` and
   `Instrument Serif` for headings, `Inter` for body, `JetBrains Mono`
   for code blocks.
2. Implement `globals.css` with the tokens taken from `armance.io`'s
   `styles4.css` (no copy of the full file — only the tokens we use).

### Task F.2 — Agent portrait component
1. Frontend test (red): `<AgentPortrait name="Armance" />` renders the
   PNG with a soft frame; `<AgentPortrait name="Aisha" />` falls back
   to a monogram with the first letter inside the frame.
2. Implement.

### Task F.3 — Fleuron divider
1. Frontend test (red): `<Fleuron />` renders the `❦` character with
   the chapter-fleuron class; it sits between sections in all panes.
2. Implement.

### Task F.4 — Calm motion (F2)
1. Frontend test (red): with `prefers-reduced-motion: reduce`, no
   element animates (no CSS transition, no JS-driven keyframe). With
   the default, fade / slide transitions on bubble appearance run at
   ~220 ms ease-out.
2. Implement a tiny `useMotionPreference` hook + a `<Reveal>` wrapper
   that applies the transitions only when allowed.

### Task F.5 — Designed empty states (F3)
1. Frontend test (red): the library pane with zero documents shows a
   designed empty state — a sentence in Instrument Serif, a fleuron, a
   subtle hint. The active-workflow pane with no run in progress shows
   *« Aucun workflow en cours. Lancez-en un via Kim. »*. The chat
   pane covered by Epic E E3.
2. Implement.

### Task F.6 — Storybook + visual regression CI
1. Set up Storybook for the frontend; every component above has a story.
2. Add a Playwright visual-regression test on the empty session page.
3. CI runs the visual regression diff against a checked-in baseline.

## Acceptance criteria (epic-level)

- [ ] A screenshot of any screen is indistinguishable in *feel* from
      `armance.io`.
- [ ] Motion is present, subtle, and fully disabled under
      `prefers-reduced-motion`.
- [ ] Every screen has a designed idle state — no raw scaffolding.
- [ ] Lighthouse: performance ≥ 90, accessibility ≥ 95.

## Out of scope

- A separate marketing landing inside the app (use `armance.io`).
- Dark mode (V3 — would need a separate palette set).
