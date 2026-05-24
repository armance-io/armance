# Web Epic B · The reading room (viewer)

> Status: **ready to implement after Epic A**.
> Part of [`web-layer-stories.md`](web-layer-stories.md).
> Build guide reference: [`web-layer.md`](web-layer.md).

## Goal

Read-only browser surfaces onto what `.armance/` already contains.
Lowest risk, highest *« this is a real product »* payoff. Pure read
endpoints plus their UI panes. The one write affordance allowed is
uploading a document into `.armance/docs/` (something a non-technical
user genuinely cannot do otherwise).

## User stories covered

- **B1** — Browse the library (indexed *feuillets* vs loaded read set).
- **B2** — Read a deliverable inline (Markdown) with download for
  pdf/docx/pptx.
- **B3** — Read past workflow runs (steps, durations, token counts,
  per-step output).

## Backend dependencies (all green)

| Dependency | Where it lives | Notes |
|---|---|---|
| Library status | `armance.storage.rag_status.get_rag_status(armance_root, cfg)` | Returns the structured dict. |
| Library state | `armance.storage.library_state` | Indexed + read set. |
| Doc ingestion | `armance.storage.ingestion.sync_docs` | For B-note (upload triggers). |
| Run list | `armance.service.workflow_runs.list_runs(armance_root, workflow_name)` | Reads `runs.json`. |
| Run loader | `armance.service.workflow_runs.load_run(armance_root, workflow_name, run_id)` | Returns the manifest. |
| Exports root | `armance.storage.paths.exports_dir(armance_root)` | Used by the download route. |

## File / module layout

```
web/backend/routes/
  library.py     GET /sessions/{sid}/library
  docs.py        POST /sessions/{sid}/docs           (upload only, see B-note)
  exports.py     GET /sessions/{sid}/exports/{filename}
  runs.py        GET /sessions/{sid}/workflows/{name}/runs
                 GET /sessions/{sid}/workflows/{name}/runs/{run_id}
                 GET /sessions/{sid}/workflows/{name}/runs/{run_id}/step/{step_id}
```

## TDD task list

### Task B.1 — `GET /sessions/{sid}/library`
1. Test (red): seed `.armance/` with a doc + index it; the route returns
   200 with a JSON body whose shape matches `get_rag_status(...)`.
2. Test (red): with a missing `embedding_provider`, the route still
   returns 200 and `available: false`. (Mirrors the V1 behaviour.)
3. Implement: call `get_rag_status` and return the dict.

### Task B.2 — `POST /sessions/{sid}/docs` (upload)
1. Test (red): `POST` with a `multipart/form-data` payload containing
   `file=<bytes>` returns 201 with `{"name": "<file>", "size": <n>}`;
   the file lands in `.armance/docs/<file>`.
2. Test (red): empty filename → 400. File > `MAX_UPLOAD_BYTES` → 413.
3. Test (red): the route **does not** call `sync_docs` itself — the
   user triggers indexing through Armance via `[EXECUTE:/library-index]`.
4. Implement.

### Task B.3 — `GET /sessions/{sid}/exports/{filename}` (download)
1. Test (red): a `.md` file in `.armance/exports/` is served with
   `Content-Type: text/markdown; charset=utf-8`; binary files (`.pdf`,
   `.docx`, `.pptx`) with `application/octet-stream`.
2. Test (red): path traversal (`../../etc/passwd`) is rejected with 400.
3. Implement using `pathlib` `resolve()` + `is_relative_to(exports_root)`
   for the path safety check.

### Task B.4 — `GET /sessions/{sid}/workflows/{name}/runs`
1. Test (red): with a workflow that has two recorded runs in
   `runs.json`, the route returns a JSON list of compact run entries
   identical to `runs.json` (id, status, started_at, ended_at,
   duration_ms, tokens_in, tokens_out, cost_usd or `null`).
2. Test (red): unknown workflow name → 404.
3. Implement: call `list_runs(armance_root, name)`.

### Task B.5 — `GET /sessions/{sid}/workflows/{name}/runs/{run_id}`
1. Test (red): the route returns the full `manifest.json` for the given
   run, byte-for-byte equal to the on-disk file.
2. Test (red): unknown `run_id` → 404.
3. Implement: call `load_run(armance_root, name, run_id)`.

### Task B.6 — `GET /sessions/{sid}/workflows/{name}/runs/{run_id}/step/{step_id}`
1. Test (red): returns the raw Markdown content of
   `.armance/exports/<name>/<run_id>/step-<step_id>.md`, with
   `Content-Type: text/markdown`.
2. Test (red): unknown step → 404; path traversal → 400.
3. Implement.

### Task B.7 — Frontend pages (Library + Deliverable + Past Runs)
1. Frontend test (red — Playwright): on `/session/<sid>`, the library
   pane renders the indexed and loaded doc lists from `GET /library`.
2. Frontend test (red): clicking a deliverable opens an inline Markdown
   reader with the correct content from `GET /exports/...`.
3. Frontend test (red): clicking a past run opens a detail view with
   per-step status, duration, tokens — pulled from `GET /workflows/.../
   runs/<id>`.
4. Implement the three panes.

### Task B.8 — Coverage gate
1. Add coverage on the `web/backend/routes/library.py`,
   `routes/docs.py`, `routes/exports.py`, `routes/runs.py` at ≥ 85 %.

## Acceptance criteria (epic-level)

- [ ] Library pane matches `/library status` exactly.
- [ ] Every `/deliverable` output is reachable from the UI within one
      click.
- [ ] `GET /workflows/<name>/runs` and `…/runs/<run_id>` return JSON
      identical to the on-disk files.
- [ ] Upload route writes into `.armance/docs/` and **does not** trigger
      indexing on its own (invariant #5: no autonomous side effect).
- [ ] No `src/armance/` files were modified.
- [ ] `pytest web/backend/tests/test_library.py test_docs.py
      test_exports.py test_runs.py -q` is green.

## Out of scope

- Editing a deliverable in place (B is read-only).
- Index / unindex / load / unload triggered by the UI directly. Those
  remain agent-driven via the chat surface (Epic C) and the
  `[EXECUTE:/library-*]` tags.
