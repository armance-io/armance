# Web PWA + mobile (Android + iOS)

> Status: **not started, transverse to V2 + V3** (verified 2026-06-04 on
> `feat/environmental-impact`: no `manifest`, no service worker, no
> `next-pwa`, empty `web/frontend/public/`; the app is responsive but not
> installable/offline).
> Part of `web-layer-stories.md`.

## Why

V3 SaaS targets users far beyond power-developers. They will open
Armance from a phone — to drop a photo of a document, to read a
deliverable on the train, to react to a checkpoint. The web app must
therefore:

- be **installable** (Add to Home Screen on iOS + Android).
- work **offline-aware** for read-only views (deliverables, past runs).
- be **responsive** down to 360 px.
- support **iOS Safari** quirks (PWA manifest, safe-area insets,
  100vh bug, audio autoplay restrictions for V3 TTS).

V2 local already benefits from PWA basics: the user can pin the
local app on their laptop's dock. V3 SaaS is where mobile becomes the
primary entry point.

## Scope per phase

| Phase | Capability | Spec |
|---|---|---|
| **V2** | Responsive layout 360 → 1920 ; touch targets ≥ 44 px ; sidebar collapses on < 768 px | §1 |
| **V2** | Web App Manifest + service worker (basic shell cache) — installable on desktop + Android Chrome / iOS Safari | §2 |
| **V2** | Offline-aware read-only views (deliverables, past runs) — read from `localStorage` cache when offline | §3 |
| **V3** | SaaS PWA polish — splash, theme-colour, status bar, iOS standalone mode quirks | §4 |
| **V3** | Push notifications (workflow run done, checkpoint pending) — opt-in | §5 |
| **V3** | Camera input — take a photo of a document, upload directly (mobile-first vision flow) | §6 |

## §1 — Responsive layout (V2)

### Breakpoints

```
xs   < 480     phone portrait    sidebar = drawer, chat full-width
sm   480–767   phone landscape   same as xs
md   768–1023  tablet portrait   sidebar collapsible, 60/40 split
lg   1024–1439 desktop           default 3-column
xl   1440+     wide desktop      4-column with right rail expanded
```

### Component constraints

- All interactive elements ≥ 44 × 44 px (Apple HIG + Android Material).
- Sidebar becomes a drawer behind a hamburger on `xs` / `sm`.
- Chat input fixed bottom with proper safe-area insets.
- React Flow workflow graph supports pinch-zoom + pan on touch.
- Tables (logs, stats, deliverables list) → cards on `xs` / `sm`.

### Tasks

```
PWA.1 — Tailwind v4 breakpoints + responsive AppShell
  1. Define breakpoints in `tailwind.config.ts`.
  2. AppShell sidebar becomes drawer at `< md`.
  3. Hamburger toggle in the header.
  4. Playwright tests: viewport 360, 768, 1280 each render the
     expected layout.

PWA.2 — Touch targets audit
  1. ESLint rule or visual regression: every clickable element ≥
     44 px.
  2. Audit + fix existing components.

PWA.3 — React Flow touch support
  1. Enable React Flow's `panOnDrag` + `pinchZoom` for touch.
  2. Playwright + Playwright-touch test: pinch-zoom works.
```

## §2 — PWA manifest + service worker (V2)

### Manifest

`web/frontend/public/manifest.webmanifest`:

```json
{
  "name": "Armance",
  "short_name": "Armance",
  "description": "Une maison d'agents qui pensent.",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#f4ede0",
  "theme_color": "#6b4f8a",
  "icons": [
    {"src": "/icons/armance-192.png", "sizes": "192x192", "type": "image/png"},
    {"src": "/icons/armance-512.png", "sizes": "512x512", "type": "image/png"},
    {"src": "/icons/armance-maskable.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    {"src": "/icons/armance.svg", "sizes": "any", "type": "image/svg+xml"}
  ],
  "lang": "fr",
  "dir": "ltr"
}
```

iOS Safari requires `<link rel="apple-touch-icon">` + `<meta
name="apple-mobile-web-app-capable" content="yes">` separately —
covered in `app/layout.tsx`.

### Service worker

`web/frontend/public/sw.js` — keep simple at V2:

- Pre-cache the app shell (`/`, `/setup`, fonts, CSS, JS bundles).
- Runtime cache for `/projects/.../exports/*` (deliverables) with
  `cache-first` strategy.
- Runtime cache for `/sessions/.../library` JSON with
  `stale-while-revalidate`.
- All other routes: `network-only` (fresh data preferred).
- On install: skip waiting + claim clients (so user picks up new
  version on next tab focus).

Use `workbox-window` library to wire it; ~5 KB on the page.

### Tasks

```
PWA.4 — Manifest + icons
  1. Generate icon set (192, 512, maskable, svg) from a single
     source SVG using `sharp`-cli or similar.
  2. Wire manifest + apple-touch-icon links in `app/layout.tsx`.
  3. Playwright test: a fresh install on Android Chrome (via
     `installprompt` event) shows the right name + icon.

PWA.5 — Service worker basics
  1. `public/sw.js` + `workbox-window` registration.
  2. Pre-cache shell on install.
  3. Test: open the app, kill the network, refresh — shell loads.
```

## §3 — Offline-aware reads (V2)

### Strategy

Three classes of data:

| Class | Examples | Offline behaviour |
|---|---|---|
| **Immutable** | Past run manifests, deliverables, library docs | Full offline cache. `cache-first`. |
| **Mutable but stable** | Library status, agents list | `stale-while-revalidate` — show cached, refresh in bg. |
| **Real-time** | Chat, SSE stream, active workflow | Online-only. Show *« Hors ligne »* banner with retry. |

### Offline banner

A small banner appears when the browser reports offline. Real-time
operations are disabled (chat input greyed, SSE stops). Read-only
navigation keeps working from the cache.

### Tasks

```
PWA.6 — Offline cache strategies
  1. Wire workbox routes per the table above.
  2. Test: with network killed, `GET /exports/...` from a cached
     deliverable still works.

PWA.7 — Offline banner
  1. Listen to `online` / `offline` events.
  2. Show / hide a small persistent banner at the top.
  3. Disable chat input + real-time controls when offline.
```

## §4 — V3 SaaS PWA polish

### Items

- Splash screen for iOS standalone mode.
- Theme-color matches the active light/dark mode (manifest can't be
  dynamic; we update `<meta name="theme-color">` at runtime).
- Safe-area insets for notched iPhones.
- iOS 100vh fix (use `100dvh` + JS fallback).
- iOS audio autoplay restriction handling (V3 TTS requires user
  gesture to start the first sound).

### Tasks (V3)

```
PWA.8 — iOS polish
  1. Generate splash screens for every device pixel-ratio.
  2. Dynamic theme-color tied to the active theme.
  3. `env(safe-area-inset-*)` in AppShell.
  4. 100dvh + JS fallback.

PWA.9 — Audio autoplay handling (V3)
  1. First TTS request → request user permission via a single visible
     button (*« Activer la lecture audio »*).
  2. Persist permission in `localStorage`.
```

## §5 — Push notifications (V3)

### Use cases

- Workflow run completed.
- Checkpoint waiting for the user.
- Mona has finished a synthesis.

Opt-in only. Tied to the user's account in V3.

### Backend

GCP Firebase Cloud Messaging (FCM). Backend stores per-user push
tokens in Firestore; sends notifications on workflow events.

### Frontend

`Notification.requestPermission()` + service worker `push` event
handler that shows a system notification with a deep link to the
relevant session / run.

### Tasks (V3)

```
PWA.10 — Backend push (V3)
  1. New collection `push_tokens` in Firestore.
  2. POST /push/subscribe stores a token for a user.
  3. Worker on run completion / checkpoint emits FCM via
     `firebase-admin`.

PWA.11 — Frontend push (V3)
  1. Settings page: toggle to enable / disable notifications.
  2. Service worker `push` handler shows the notification.
  3. Click → opens the matching URL.
```

## §6 — Camera input (V3, mobile-first)

### Use case

User opens Armance on phone, points camera at a document, snaps a
photo, photo is uploaded as an image into the library, vision
pipeline kicks in. Cuts friction massively vs *« scanner d'abord, puis
téléverser »*.

### Frontend

`<input type="file" accept="image/*" capture="environment">` opens
the camera directly on mobile. Single button on the library pane.
Desktop browsers fall back to a normal file picker.

### Tasks (V3)

```
PWA.12 — Camera capture button
  1. Library pane gains a *« Photographier »* button on mobile.
  2. The input opens the camera; the chosen / taken photo uploads
     directly via POST /library/docs.
  3. Playwright (mobile emulation) test.
```

## Acceptance criteria

### V2
- [ ] App is installable on Android Chrome and iOS Safari.
- [ ] Layout works from 360 px to 1920 px without breaks.
- [ ] App shell loads offline after first visit.
- [ ] Past runs and deliverables read offline from the cache.
- [ ] React Flow workflow graph navigable by touch.

### V3
- [ ] iOS PWA polish (splash, theme-color, safe-area, 100dvh).
- [ ] Push notifications opt-in works for workflow + checkpoint
      events.
- [ ] Camera capture from mobile uploads directly into the library.

## Open questions

- **Q-PWA.1** — Service worker scope: per-project (each project
  is a different `start_url`) or global? Reco: global; the SW just
  caches the shell + immutable artefacts.
- **Q-PWA.2** — Splash screen art: portrait of Armance, or fleuron
  + brand mark? Reco: fleuron + brand mark (sober).
- **Q-PWA.3** — Push notifications require HTTPS. V2 localhost
  doesn't need them but V3 SaaS is HTTPS by default. No issue.
