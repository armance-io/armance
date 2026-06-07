# Armance Web — Local Development

How the web layer is built, how to iterate on it, and how to test your
changes **without committing or pushing**. For the user-facing launch story
see [`README.md`](../README.md#running-the-web-client-ui).

## Layout

```
src/armance/web/backend/     FastAPI app — ships INSIDE the armance wheel
  main.py                    create_app(): API + static-SPA serving
  routes/                    25 routers (mounted at root AND /api)
  tests/                     163 offline tests (not shipped to users)
src/armance/web_dist/        Built static UI — GITIGNORED build artifact
web/frontend/                Next.js 16 sources
  out/                       `pnpm build` output (gitignored)
```

The backend lives in the package so `armance web` works after `pip install`.
The frontend is built to static files and **bundled into the wheel** at
`src/armance/web_dist/` — it is a build artifact, never committed.

## The two ways to run the UI

### A. Dev mode — hot reload (use this while editing the UI)

Two processes, no bundle needed. Fastest feedback loop.

```bash
# terminal 1 — API
armance web --no-browser            # FastAPI on :8000

# terminal 2 — UI with hot reload
cd web/frontend
pnpm install
pnpm dev                            # Next.js on :3000, proxies /api → :8000
```

Open <http://localhost:3000>. Edits to `web/frontend/src/**` reload live.
`pnpm dev` does **not** use `web_dist`; it serves from source.

### B. Bundled mode — one process (what users get)

Build the static bundle, then a single `armance web` serves API + UI from
`:8000`, exactly like a released wheel:

```bash
armance web --build                 # pnpm build → src/armance/web_dist/, then serve
```

`--build` needs Node + pnpm. Use this to verify the *real* user experience
(static export quirks, SPA fallback, same-origin `/api`) before shipping.

To build the bundle without launching the server:

```bash
cd web/frontend && ARMANCE_STATIC_EXPORT=1 pnpm build
rm -rf ../../src/armance/web_dist && cp -r out ../../src/armance/web_dist
# then:
armance web                         # serves the freshly built bundle
```

## Testing changes without commit & push

Everything below runs against your working tree — nothing is committed.

```bash
# Backend (from web/; web deps ship in core — no extra)
cd web && uv run pytest ../src/armance/web/backend/tests/      # 163 tests

# Frontend
cd web/frontend
pnpm typecheck            # tsc --noEmit (covers .test.ts too)
pnpm lint                 # eslint --max-warnings 0
pnpm test                 # vitest + coverage gate
pnpm e2e                  # playwright (auto-starts `pnpm dev`)
```

Manual smoke of the bundled path (proves a clean install would work) without
touching git or PyPI:

```bash
scripts/build_release.sh            # builds wheel WITH the UI, verifies it
python -m venv /tmp/v && /tmp/v/bin/pip install "dist/"*.whl
cd /some/project && /tmp/v/bin/python -m uvicorn armance.web.backend.main:app --port 8000
# browse http://127.0.0.1:8000 — same as `pip install armance && armance web`
```

## How bundling reaches users

- `pip install git+…` or a plain `uv build` → **API-only** wheel (no bundle;
  `web_dist` is gitignored). `armance web` then prints a note and serves the
  API only.
- **Release wheels** (PyPI) are built with `scripts/build_release.sh`, which
  runs `pnpm build`, copies `out/` → `src/armance/web_dist/`, builds the
  wheel, and asserts the UI shipped. That is the wheel that makes
  `pip install armance && armance web` serve the full UI with Python only.

See [`CONTRIBUTING.md`](../CONTRIBUTING.md#releasing-bundling-the-web-ui).

## Architecture notes (gotchas)

- **Dynamic routes + static export.** Each `[pid]/[sid]/…` route is a thin
  server `page.tsx` (exports `generateStaticParams` → one `_` sentinel
  shell) rendering a `"use client"` `*View.tsx`. Views read ids from the
  **live URL** via `lib/routeParams.ts` (`useRouteParams`), never the
  sentinel — so a hard load of `/projects/REAL/…` shows real data.
- **API vs SPA URLs collide** (`/projects/{pid}/…` is both). The backend
  serves the SPA only for `Accept: text/html` GETs; data calls go to
  `/api/*`. API routers are mounted at root (tests, `Accept: */*`) and `/api`
  (browser). See `backend/main.py::_install_spa`.
- **Coverage gate** (`web/frontend/vitest.config.ts`): global floor +
  per-file 100/95 locks on `lib/routeParams.ts` and `lib/graphLayout.ts`.
  Visual/React-Flow components are covered by Playwright, excluded from the
  unit gate.
