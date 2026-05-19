# Armance V2 — Web Layer Implementation Guide

> Audience: a medium-skill agent or engineer who needs to land the V2 web
> port without rewriting any service-layer code. Self-contained — read
> top to bottom, no jumping required.
>
> Prereqs: V1 is green (`pytest tests/ -q` → 889/0; ruff clean;
> `scripts/check_invariants.sh` → 31/31). `git log --oneline` shows the
> recent P1.3–P1.7 commits.

---

## 0. TL;DR

The service layer is already frontend-agnostic. You build:

1. A **FastAPI app** that owns Sessions and a per-session **EventBus**.
2. A `WebCheckpointHandler` that bridges Armance's `CheckpointHandler`
   protocol to an HTTP/SSE round-trip — that's the *only* glue.
3. A small **Next.js front-end** consuming REST + SSE.

You do **not** rewrite handlers, do **not** rewrite agents, do **not**
touch the service layer.

---

## 1. What V1 already gives you

| Capability | Module |
|---|---|
| Slash command dispatch | `armance.service.tui_bridge.dispatch_input(text, ctx) -> (reply, agent_name)` |
| Frontend-agnostic prompting | `armance.service.checkpoint.CheckpointHandler` (Protocol) |
| Event types ready for SSE | `armance.transport.dto.Event`, `armance.transport.events` |
| Per-session bus | `armance.service.events.LocalEventBus` |
| Session state on disk | `.armance/sessions/<id>/` (state.json, ledger.json, conversation.md) |
| LLM client registry | `armance.core.protocols.llm.get_client` |
| Library + read state | `armance.storage.library_state`, `storage.ingestion.sync_docs` |
| Cost estimate | `armance.service.cost.estimate_workflow` |

**There is no questionary call inside `service/handlers.py` anymore.**
Every interactive prompt goes through `ctx.checkpoint_handler`. Your
`WebCheckpointHandler` plugs in there.

---

## 2. The minimum viable surface

```
POST   /sessions                    -> { id }                      start
GET    /sessions/{id}               -> { state, ledger, agents }   resume
POST   /sessions/{id}/turn          -> { ack, event_url }          submit text
GET    /sessions/{id}/events        SSE                            stream events
POST   /sessions/{id}/checkpoint    body: { id, content, is_abort } answer a prompt
POST   /sessions/{id}/docs          multipart                      upload doc
GET    /sessions/{id}/exports/{f}   binary                         download deliverable
GET    /sessions/{id}/library       -> library status              indexed + read
```

Eight endpoints, two stream types. No more.

---

## 3. The one piece of glue you have to write

```python
# web/backend/checkpoint.py
import asyncio
import uuid

from armance.service.checkpoint import (
    Checkpoint,
    CheckpointHandler,
    CheckpointResponse,
)


class WebCheckpointHandler(CheckpointHandler):
    """Bridges Armance's CheckpointHandler protocol to a web round-trip.

    When the service layer hits a checkpoint, we:
      1. Mint a checkpoint id.
      2. Emit an SSE 'checkpoint_requested' event to the connected client.
      3. Wait on an asyncio.Future for the matching POST /sessions/{id}/checkpoint.
    """

    def __init__(self, event_bus, timeout: float = 600.0) -> None:
        self._bus = event_bus
        self._timeout = timeout
        self._pending: dict[str, asyncio.Future[CheckpointResponse]] = {}

    async def prompt(self, checkpoint: Checkpoint) -> CheckpointResponse:
        cp_id = f"{checkpoint.id}:{uuid.uuid4().hex[:8]}"
        fut: asyncio.Future[CheckpointResponse] = asyncio.get_event_loop().create_future()
        self._pending[cp_id] = fut
        await self._bus.publish({
            "type": "checkpoint_requested",
            "checkpoint_id": cp_id,
            "kind": checkpoint.kind,
            "prompt": checkpoint.prompt,
            "options": checkpoint.options,
        })
        try:
            return await asyncio.wait_for(fut, timeout=self._timeout)
        finally:
            self._pending.pop(cp_id, None)

    def resolve(self, cp_id: str, content: str, is_abort: bool = False) -> bool:
        """Called from POST /sessions/{id}/checkpoint."""
        fut = self._pending.get(cp_id)
        if fut is None or fut.done():
            return False
        fut.set_result(CheckpointResponse(content=content, is_abort=is_abort))
        return True
```

That's the whole bridge. ~40 LOC. Everything else is wiring.

---

## 4. Step-by-step implementation

### 4.1 Backend scaffold (~1 day)

```
web/backend/
  __init__.py
  main.py            FastAPI app + CORS + lifespan
  state.py           SessionStore: { id -> (Session, LoopContext, EventBus, WebCheckpointHandler) }
  checkpoint.py      WebCheckpointHandler (from §3)
  routes/
    sessions.py      POST/GET /sessions, GET /sessions/{id}
    turn.py          POST /sessions/{id}/turn  (calls dispatch_input)
    events.py        GET /sessions/{id}/events  (SSE)
    checkpoint.py    POST /sessions/{id}/checkpoint
    docs.py          POST /sessions/{id}/docs   (multipart, calls sync_docs)
    library.py       GET /sessions/{id}/library (calls library_ops.cmd_library)
    exports.py       GET /sessions/{id}/exports/{filename}
```

**Session creation** does what `cli.cmd_run` does today, minus the TUI launch:

```python
from armance.config import load_config, ensure_armance_tree
from armance.service.session import start_or_resume, Session
from armance.service.llm_service import TokenLedger, set_ledger
from armance.service.tui_bridge import make_loop_context

def new_session(armance_root: Path):
    cfg = load_config(armance_root.parent)
    ensure_armance_tree(armance_root.parent, cfg)
    state = start_or_resume(armance_root, resume=False)
    session = Session(state, armance_root)
    ledger = TokenLedger(persist_path=Path(state.ledger_path)) if state.ledger_path else TokenLedger()
    set_ledger(ledger)
    bus = ...  # asyncio.Queue-backed
    handler = WebCheckpointHandler(bus)
    ctx = make_loop_context(armance_root, cfg, state, session, ledger,
                            checkpoint_handler=handler)
    return session, ctx, bus, handler
```

**Turn submission** is one call:

```python
@router.post("/sessions/{sid}/turn")
async def submit_turn(sid: str, body: TurnIn):
    sess = STORE.get(sid)
    asyncio.create_task(_run_turn(sess, body.text))    # fire and forget
    return {"ack": True, "event_url": f"/sessions/{sid}/events"}

async def _run_turn(sess, text):
    from armance.service.tui_bridge import dispatch_input
    reply, agent_name = await dispatch_input(text, sess.ctx)
    await sess.bus.publish({"type": "turn_completed", "reply": reply, "agent": agent_name})
```

**SSE stream** is `sse_starlette` over the bus:

```python
from sse_starlette.sse import EventSourceResponse

@router.get("/sessions/{sid}/events")
async def stream(sid: str):
    sess = STORE.get(sid)
    async def gen():
        async for evt in sess.bus.subscribe():
            yield {"event": evt["type"], "data": json.dumps(evt)}
    return EventSourceResponse(gen())
```

**Checkpoint resolution** calls back into the handler:

```python
@router.post("/sessions/{sid}/checkpoint")
async def resolve(sid: str, body: CheckpointIn):
    sess = STORE.get(sid)
    ok = sess.handler.resolve(body.checkpoint_id, body.content, body.is_abort)
    return {"resolved": ok}
```

**Docs upload** delegates to `sync_docs`:

```python
@router.post("/sessions/{sid}/docs")
async def upload(sid: str, file: UploadFile):
    sess = STORE.get(sid)
    target = sess.ctx.armance_root / "docs" / file.filename
    target.write_bytes(await file.read())
    # The user will trigger indexing through Armance ([EXECUTE:/library-index])
    # or via the library endpoint — never silently here.
    return {"name": file.filename, "size": target.stat().st_size}
```

### 4.2 Frontend (~1.5 days)

Stack: Next.js 16 App Router, Tailwind v4, Zustand, `eventsource-polyfill`.

Three pages:

1. `/workspace` — list of sessions + `New project` modal → `POST /sessions`.
2. `/session/[id]` — three-column layout:
   - Left: docs rail (uploads, `GET /sessions/{id}/library` → indexed +
     read state, "Index" / "Load" buttons that mint a `/turn` calling
     `/library index <file>` or `/library load <file>`).
   - Centre: streamed deliberation (SSE consumer, renders messages in
     order; checkpoint requests open a drawer/modal).
   - Right: agents + workflows (calls `GET /sessions/{id}` for the
     ledger snapshot, refreshes every 2s).
3. `/session/[id]/checkpoint` — *not a page*, a drawer triggered by
   `checkpoint_requested` SSE events. Renders three forms based on
   `kind`: text (textarea), select (dropdown), confirm (yes/no
   buttons). Submitting calls `POST /sessions/{id}/checkpoint`.

### 4.3 Cost & feature parity sanity

The web client must hit feature parity with the TUI before being shipped:

- [ ] First-session greeting (Armance lists docs in `.armance/docs/`)
- [ ] `/library index|load|unload|unindex|status` end-to-end
- [ ] Malik recruitment with `[EXECUTE:/recruit]` YAML round-trip
- [ ] Kim workflow design + `[EXECUTE:/workflow-design]` checkpoint chain
- [ ] `/workflow run` with cost preflight checkpoint + checkpoint steps
- [ ] `/deliverable pdf|docx|pptx|md` + download endpoint
- [ ] Language switch (config edit + reload session)

---

## 5. Architectural invariants you must NOT break

1. **No service code under `web/`**. The backend is a transport adapter.
   Anything that looks like business logic belongs in `armance.service.*`.
2. **No new `[EXECUTE:/...]` tags**. The agent prompt-driven side-effect
   contract is the only way to trigger anything destructive or
   side-effectful. If you need a new action, add it as a tag and
   intercept it in `host_agent.py` or the relevant `*_ops.py` module.
3. **No new questionary**. Anything that needs user input goes through
   `CheckpointHandler`.
4. **Layer rule survives**. `web/` may import from `armance.service.*`
   and `armance.transport.*`. It must never bypass them.

---

## 6. Suggested commit cadence

| # | Commit | Lines (target) |
|---|---|---|
| 1 | `feat(web): scaffold FastAPI app + SessionStore + /sessions endpoints` | ~150 |
| 2 | `feat(web): WebCheckpointHandler + SSE stream` | ~120 |
| 3 | `feat(web): POST /turn + dispatch_input wiring` | ~80 |
| 4 | `feat(web): docs upload + library status endpoints` | ~80 |
| 5 | `feat(web): deliverable download endpoint` | ~50 |
| 6 | `feat(web/frontend): scaffold Next.js + workspace page` | ~300 |
| 7 | `feat(web/frontend): session page (3-column) + SSE consumer` | ~400 |
| 8 | `feat(web/frontend): checkpoint drawer (text/select/confirm)` | ~150 |
| 9 | `chore(web): docker-compose backend + frontend services` | ~50 |

Total: **~1.4k LOC**, all in `web/`. No `src/armance/` changes expected.
If you find yourself editing `src/armance/`, stop and ask whether the
change belongs in V1 (then PR it separately).

---

## 7. Things you'll need that already exist

- **Free-tier models for QA**: call
  `armance.providers.model_discovery.discover_openrouter_models()` →
  free tier list comes back. Pick two for QA fixtures.
- **Cost estimate**:
  `armance.service.cost.estimate_workflow(wf, ctx.agents, prompt, prices_override=cfg.prices)`.
- **Library status JSON**:
  `armance.storage.rag_status.get_rag_status(armance_root, cfg)` returns
  the structured dict — re-serialise to JSON directly.

---

## 8. Where it can go wrong

| Symptom | Most likely cause |
|---|---|
| Checkpoints never resolve | Your handler did not register `cp_id` in `_pending` before publishing the event — race window. Mint the id and store the future *before* `bus.publish`. |
| SSE stream cuts after first event | Missing `await` on `bus.publish`, or the queue was instantiated per-request instead of per-session. |
| Library shows "déjà retenu" for un-indexed doc | The boot path is silently calling `sync_docs` without a config. V1 has this guarded — do not call sync_docs from `web/backend/main.py` lifespan. |
| Agent replies in English on a French project | Your session creation forgot `set_language(cfg.language)`. Call it in `new_session` (see §4.1). |
| `OPENROUTER_API_KEY` missing in container | `Config` overlay reads `.env` from the armance_root, not from the container env. Pass through with `--env-file .env`. |

---

## 9. Done criteria

- All eight endpoints respond with shape documented in §2.
- A full session can be driven from the browser: greet → docs → library → recruit → design → run → deliverable.
- `pytest web/backend/tests/ -q` green.
- Frontend Lighthouse score ≥ 90 for performance + accessibility.
- `docker compose up` boots backend + frontend together; visiting
  `localhost:3000` lands on `/workspace` with a working `New project`
  modal.

That's V2.

---

## 10. After V2 (V3 teasers)

These are *not* in scope for V2. Mentioned only so you don't accidentally
build them now:

- Multi-tenant auth + RBAC (V2 stays single-user on localhost / trusted LAN).
- MCP server exposing Armance skills.
- A2A endpoint for Malik-recruited specialists.
- OpenTelemetry trace ids on every LLM call.

When the time comes, see `roadmap/04_roadmap.md` Phase P3.
