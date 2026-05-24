# Web Epic A · Transport & session spine

> Status: **ready to implement** — every backend dependency already
> exists.
> Part of [`web-layer-stories.md`](web-layer-stories.md).
> Build guide reference: [`web-layer.md`](web-layer.md) §§ 0 to 3.

## Goal

Stand up the FastAPI process that hosts a per-tab `LoopContext`, serves
the same `.armance/` folder the TUI uses, and bridges the existing
`CheckpointHandler` protocol to an HTTP round-trip. Nothing user-visible
ships from this epic alone, but everything else depends on it.

## User stories covered

- **A1** — `armance web` serves the current `.armance/` session in a
  browser tab, no separate install.
- **A2** — `WebCheckpointHandler` implements the existing
  `CheckpointHandler` Protocol so a checkpoint raised by any agent
  surfaces as a real form in the browser.
- **A3** — Live updates without manual refresh (polling, no WebSocket
  required at V2).
- **A4** — Optional LAN bind so a colleague on the same network can
  watch the session read-only. One driver, N watchers.

## Backend dependencies (all green)

| Dependency | Where it lives | Notes |
|---|---|---|
| Public entry point | `armance.service.tui_bridge.dispatch_input(text, ctx) -> (reply, agent_name)` | Stateless, reentrant. |
| Checkpoint protocol | `armance.service.checkpoint.CheckpointHandler` | `kind: text | select | confirm`. |
| Event bus | `armance.service.events.LocalEventBus` | JSONL + `asyncio.Queue`. |
| Session creation | `armance.service.session.start_or_resume` + `Session` | |
| Token ledger | `armance.service.llm_service.TokenLedger` + `set_ledger` | Per-session file. |
| Loop context factory | `armance.service.tui_bridge.make_loop_context` | |
| Layered config | `armance.config.load_config` + `ensure_armance_tree` | |
| Filesystem lock | `armance.storage.filesystem.lockfile` | Already handles concurrent writes. |

## File / module layout

```
web/
  backend/
    __init__.py
    main.py            FastAPI app + CORS + lifespan
    state.py           SessionStore: {sid -> (Session, LoopContext, EventBus, WebCheckpointHandler)}
    checkpoint.py      WebCheckpointHandler (the ~40 LOC bridge)
    sse.py             EventSourceResponse helper (sse-starlette wrapper)
    routes/
      sessions.py      POST/GET /sessions, GET /sessions/{id}
      turn.py          POST /sessions/{id}/turn
      events.py        GET /sessions/{id}/events (SSE)
      checkpoint.py    POST /sessions/{id}/checkpoint
      docs.py          POST /sessions/{id}/docs
      library.py       GET /sessions/{id}/library
      exports.py       GET /sessions/{id}/exports/{filename}
    tests/
      conftest.py
      test_*.py        one test file per route + WebCheckpointHandler
  pyproject.toml       fastapi, sse-starlette, uvicorn, httpx (test), pytest, pytest-asyncio
```

No `src/armance/` changes are expected.

## TDD task list

> Each task is one PR. Tests first; implementation only once the test
> red-fails for the right reason.

### Task A.0 — Scaffold + CI green
1. Create `web/backend/__init__.py`, `web/backend/main.py` with a
   `lifespan` that creates / disposes the `SessionStore`.
2. Add `web/pyproject.toml` with `fastapi`, `sse-starlette`, `uvicorn`,
   `pytest`, `pytest-asyncio`, `httpx`.
3. Add `web/backend/tests/conftest.py` exposing a `client: TestClient`
   fixture and an `armance_root: Path` `tmp_path` fixture.
4. Write the smallest healthcheck test: `GET /healthz → 200, {"ok": True}`.
5. Implement `/healthz`. CI green.

**Acceptance** — `cd web && pytest -q` is green; `uvicorn
backend.main:app --reload` boots without error.

### Task A.1 — `SessionStore` + `POST /sessions`
1. Test (red): `POST /sessions` body `{"armance_root": "<tmp>"}` returns
   201 with `{"id": "<sid>"}`; on disk, `<tmp>/.armance/sessions/<sid>/state.json`
   exists.
2. Implement `SessionStore.new(armance_root)` calling
   `ensure_armance_tree`, `start_or_resume(resume=False)`, building the
   `LoopContext` via `make_loop_context`. Cache `(Session, LoopContext,
   EventBus, WebCheckpointHandler)` by `sid`.
3. Implement the route.

**Acceptance** — round-trip test green; second `POST` mints a new sid.

### Task A.2 — `GET /sessions/{sid}` (resume)
1. Test (red): after a `POST /sessions`, `GET /sessions/{sid}` returns
   200 with `{"state": {...}, "agents": [...], "language": "..."}`. A
   non-existent sid returns 404.
2. Implement the route delegating to `SessionStore.get(sid)` and a
   `to_dict()` helper on the store entry.

**Acceptance** — same as test.

### Task A.3 — `WebCheckpointHandler` unit
1. Test (red): instantiate the handler with a fake bus; `await
   handler.prompt(Checkpoint(...))` blocks; calling
   `handler.resolve(cp_id, "answer")` resolves the future with the
   matching `CheckpointResponse`. Cover the `is_abort=True` branch.
2. Test (red): a `prompt` with no matching `resolve` within `timeout`
   raises `asyncio.TimeoutError`. (`timeout=0.05` in the fixture.)
3. Implement per the sketch in [`web-layer.md`](web-layer.md) § 3.

**Acceptance** — three tests green; coverage on `WebCheckpointHandler`
≥ 90 %.

### Task A.4 — `POST /sessions/{sid}/turn`
1. Test (red): monkeypatch `dispatch_input` to return
   `("hello", "system-context")`; `POST /sessions/{sid}/turn` with body
   `{"text": "bonjour"}` returns 202 with `{"ack": true, "event_url":
   "/sessions/<sid>/events"}`; assert `dispatch_input` was awaited with
   `("bonjour", ctx)`.
2. Test (red): the bus receives a `turn_completed` event whose `reply`
   and `agent` match the mocked return.
3. Implement the route with `asyncio.create_task(_run_turn(...))`.

**Acceptance** — both tests green; the route returns synchronously
before the dispatch finishes.

### Task A.5 — `GET /sessions/{sid}/events` (SSE)
1. Test (red): subscribe to the SSE stream with `httpx.AsyncClient`,
   publish two events on the bus, assert both are received in order with
   their `event` and `data` fields populated. Close the client; the bus
   subscriber is removed.
2. Implement using `sse-starlette` per the sketch.

**Acceptance** — test green; no event lost; no zombie subscribers after
client disconnect.

### Task A.6 — `POST /sessions/{sid}/checkpoint`
1. Test (red): with a `WebCheckpointHandler` registered, send `POST
   /sessions/{sid}/checkpoint` with `{"checkpoint_id": "<cp_id>",
   "content": "yes", "is_abort": false}`; assert it returns 200
   `{"resolved": true}` and the matching `prompt()` future resolves.
2. Test (red): unknown `cp_id` returns 200 `{"resolved": false}` (no
   500).
3. Implement.

**Acceptance** — both tests green; checkpoint round-trip works end to
end.

### Task A.7 — `armance web` CLI
1. Test (red): `armance web --port 0` boots, prints the chosen port,
   and `GET /healthz` answers; `--bind 127.0.0.1` is the default.
2. Implement a `cmd_web` in `src/armance/cli.py` that wraps
   `uvicorn.run` with the FastAPI app from `web/backend/main.py`. Add
   the entry to the CLI dispatcher.

**Acceptance** — `armance web` starts the server; the test passes
deterministically (random port, then graceful shutdown).

### Task A.8 — LAN bind (opt-in)
1. Test (red): `armance web --bind 0.0.0.0` boots and a request from
   `127.0.0.1:<port>` still works. (Hard to assert from a second NIC in
   CI; the test just covers the bind option survives, no SSL.)
2. Implement the `--bind` flag wired to `uvicorn.run`. Default stays
   `127.0.0.1`. Log a warning when binding `0.0.0.0`: *« LAN exposure:
   anyone on this network can read this session. Driver-only writes. »*

**Acceptance** — flag works; default unchanged; warning logged.

### Task A.9 — Read-along guard (A4)
1. Test (red): with one driver `sid` minted, a second tab calls
   `POST /sessions/{sid}/turn` and receives 409 `{"error":
   "read_along_only"}`. The second tab can still `GET /events` and
   `GET /sessions/{sid}`.
2. Implement a per-`sid` driver lock in `SessionStore`: the **first**
   `(client_id, sid)` pair to `POST /turn` becomes the driver; others
   are watchers. `client_id` is generated client-side and sent as a
   cookie or header.

**Acceptance** — test green; the TUI is untouched (no driver concept
in the CLI path).

### Task A.10 — Coverage gate
1. Configure `pytest --cov=backend --cov-fail-under=85` in
   `web/pyproject.toml`.
2. Add a CI workflow that runs the web tests on every PR.

**Acceptance** — coverage gate enforced; CI green.

## Acceptance criteria (epic-level)

- [ ] `armance web` boots, binds 127.0.0.1 by default.
- [ ] A `POST /sessions` writes the same `.armance/sessions/<id>/`
      content the TUI writes.
- [ ] A checkpoint raised by any agent surfaces in the browser within
      one polling cycle (~1 s).
- [ ] LAN bind is explicit (`--bind`) and read-along is enforced.
- [ ] `pytest web/` ≥ 85 % coverage on `web/backend/`.
- [ ] No `src/armance/` files were modified.

## Out of scope (handled in other epics)

- The viewer pages B1–B3 (Epic B).
- The chat UI C1–C5 (Epic C).
- The pipeline view D1–D3 (Epic D).
- Onboarding E1–E3 (Epic E).
- Visual polish F1–F3 (Epic F).
