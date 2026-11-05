# Library freshness — replace, date, signal (KISS)

> Status: **proposed, design approved** (maintainer, 2026-06-21).
> **Verified against `armance-io/armance@main` on 2026-06-21** — file paths,
> table schemas and command surfaces below were checked against the live code.
> Author: RAG versioning/temporality thread, 2026-06-21.

## Problem

The library (RAG over user docs, `RagService` / `storage/rag_index.py`) is
freshness-blind. Two real situations break it:

1. **A document is revised** — `roadmap_v1.pptx` … `roadmap_v5.pptx`. Every copy
   left in `.armance/docs/` gets chunked into the same `sqlite-vec` store and
   retrieved by similarity, so an agent can answer from a stale plan.
2. **Two *different* documents contradict each other** — e.g. meeting notes from
   different dates. Both legitimately belong in the corpus; the agent has no
   signal for which is more recent or which wins.

These need **two small, distinct mechanisms** — not a version-control system:

- For (1): **replace**. Drop the old, index the new. The agent only ever sees
  the current document. No version concept exposed.
- For (2): **an optional, user-set date** per document, used as a recency
  tie-breaker and shown to the agent, which **prefers the most recent and
  signals the contradiction** instead of guessing.

File mtime is unreliable (copying resets it), so the date is **user-supplied and
optional**. No date → the agent treats sources as equally current and signals
the conflict rather than picking.

## Design (four primitives, nothing more)

1. **Replace** — one action archives the old file (`.armance/.archive/`),
   unindexes its chunks, indexes the new file. UX: one *Update* button. Under
   the hood it is the existing unindex+index, made atomic.
2. **Optional `date`** — a nullable per-document field in the existing
   `manifest.json`. No new database, no new file.
3. **Provenance header** — every RAG chunk injected into a prompt is prefixed
   with `[<doc_id> · <date|undated>]` so the agent always sees source + recency.
4. **Signal, don't guess** — a system-prompt rule: prefer the most recent dated
   source; when sources disagree, tell the user. Contradictions are recorded
   through the **existing** claims ledger (`service/claim_ledger_service.py`,
   `verify_claim`) — no new code path.

Plus two small **context-freshness fixes** (same "use the freshest thing"
principle, on the conversation side):

5. **Freeze prefers the latest stance** — when Armance compiles `L0 + cache`
   into a new `L0` (`service/agents/host_agent.py`), the prompt is told the
   `cache` is authoritative over a contradicting `L0`, so a changed opinion
   does not leave both stances in the brief.
6. **Workflows ignore the pending cache** — a workflow run uses the frozen `L0`
   only, never the raw uncommitted `cache.md`.

## UX — how it works for the user

In the library panel (TUI `/library`, web viewer — see
`web-b-viewer.md`), per document row:

- **Update** — file picker → the old document is archived out of the index and
  the new one is indexed in its place. One click replaces "delete old, upload
  new". *(Solves case 1.)*
- **Delete** — unindex + archive.
- **Date** — an editable, optional "document date" field, blank by default.
  *(Solves case 2.)*

When the user drops a document that overlaps an existing one, Armance (which
already greets new docs via [`auto-embed-discovery`](auto-embed-discovery.md))
may ask **once**: *"Plus récent que `notes-2026-03.md` ? Une date ?"* Otherwise
the date field simply sits there for the user to fill.

Agent-side, a retrieved chunk reads `[notes-réunion · 2026-06-10] …`. Two
conflicting chunks → the agent prefers the newer date and flags the
disagreement; with no dates it flags without picking. Workflows see only the
current indexed documents + the frozen context.

There is **no "version" concept exposed to the user** — only *replace*, *date*,
*signal*.

---

## Implementation tasks

> TDD. Each task: file(s), change, test. Verify exact signatures in the named
> file before editing — paths confirmed against `armance@main`, line numbers
> are approximate. No users in prod → **no migration / back-compat**.

### Task 1 — `replace` operation + command

**Files:** `src/armance/service/library_ops.py`,
`src/armance/storage/library_state.py` (archive helper),
`tests/service/test_library_replace.py` (new).

- Add `_replace(ctx, old_filename: str, new_path: Path)` to `library_ops.py`:
  1. Move `.armance/docs/<old_filename>` → `.armance/.archive/<old_filename>`
     (use `paths.archive_dir`; on name clash suffix a timestamp).
  2. Unindex the old document — reuse the existing `_unindex` path
     (`RagService` delete by `doc_id`; remove from `manifest.json` /
     `read.json` via `library_state`).
  3. Copy `new_path` into `.armance/docs/`, then index it via the existing
     `_index` path.
  4. Return a one-line summary (archived X, indexed Y).
- Wire the user command `/library replace <old> <new>` in `cmd_library`, and an
  Armance-only intercept tag `[EXECUTE:/library-replace:<old>:<new>]` next to
  the existing `[EXECUTE:/library-status]` (same allow-list as
  `/library-configure-embedding`).

**Test:** index doc A, `replace(A, B)` → A's chunks absent from
`RagService.query`, B's present, A present under `.archive/`, `manifest.json`
no longer lists A.

### Task 2 — optional per-document `date` in `manifest.json`

**Files:** `src/armance/storage/library_state.py` (or wherever
`ingestion.sync_docs` owns `manifest.json`), `tests/storage/test_doc_date.py`.

- Extend each `manifest.json` entry from a bare filename to
  `{"name": <file>, "date": <ISO8601|null>}` (keep it a dict keyed by filename
  if simpler; the only new field is `date`, default `null`).
- Add pure helpers: `get_doc_date(armance_root, filename) -> str | None` and
  `set_doc_date(armance_root, filename, date: str | None) -> None`
  (validate ISO `YYYY-MM-DD`; raise on malformed).
- `sync_docs` preserves an existing `date` when re-indexing the same file.
- Command `/library date <file> <YYYY-MM-DD>` + tag
  `[EXECUTE:/library-date:<file>:<date>]` (Armance-only) calling `set_doc_date`.

**Test:** `set_doc_date` then `get_doc_date` round-trips; re-`sync_docs`
keeps the date; malformed date rejected; default is `None`.

### Task 3 — provenance header on injected RAG chunks

**Files:** the RAG-injection formatter — `service/context_service.py`
(`enrich_for_agent`) and/or `service/agents/specialist_runner.py`
(`_build_layered_context`); `tests/service/test_rag_provenance.py`.

- Where retrieved `Chunk`s are rendered into prompt text, prefix each with
  `[<doc_id> · <date or "undated">]` on its own line, where `date` comes from
  `get_doc_date(doc_id)` (Task 2). `Chunk` already exposes `doc_id`.
- One small pure helper `format_chunk_provenance(chunk, date) -> str` so it is
  unit-testable without an LLM.

**Test:** a chunk from a dated doc renders `[roadmap · 2026-06-10]`; from an
undated doc renders `[roadmap · undated]`; header precedes the chunk text.

### Task 4 — recency + contradiction prompt rule

**Files:** the shared RAG-context system-prompt block (the section that
introduces the injected `--- Context ---` / library chunks; grep the prompt
templates under `service/agents/` or `prompts/`); `tests/` prompt-presence
assertion.

- Add a short rule to that block: *"Sources are tagged `[doc · date]`. When two
  sources conflict, prefer the most recent date and tell the user they disagree
  (cite both). If neither is dated, say so and do not pick silently."*
- No new code path. When an agent records an assertion, the existing claims
  ledger (`verify_claim(..., 'disputed', contradicting_claim=…)`) already
  captures the contradiction with provenance.

**Test:** assert the rule string is present in the assembled RAG context block.

### Task 5 — freeze prefers the latest stance (context fix)

**Files:** `src/armance/service/agents/host_agent.py` (the LLM-compile freeze,
~the `call_with_ledger` compile of `prev L0 + cache`); `tests/`.

- In the freeze compile prompt, add: *"The pending cache is more recent than the
  existing L0. Where they conflict, the cache wins; drop the superseded stance
  and note what changed (one `CHANGED:` line)."*

**Test:** with a stubbed compile LLM, a cache note that contradicts L0 produces
an L0 that keeps the new stance (assert the prompt carries the rule; the
stub returns the new stance).

### Task 6 — workflows ignore the pending cache (context fix)

**Files:** `src/armance/service/agents/specialist_runner.py`
(`_build_layered_context`); `tests/service/test_workflow_no_raw_cache.py`.

- `_build_layered_context` currently appends `read_cache()` in both chat and
  workflow paths. Add an `is_workflow: bool` (or reuse an existing run-mode
  flag) and **skip the pending cache** when `is_workflow` is true — the run uses
  the frozen `L0` only. Chat path is unchanged.

**Test:** with a non-empty `cache.md`, a workflow-mode build does **not** contain
the cache body; a chat-mode build still does.

### Task 7 — web *Update* + *Delete* buttons

**Files:** web library viewer (Epic B — `web-b-viewer.md`),
`service/library_web_ops.py` + the FastAPI route; component test.

- Backend: a `POST …/library/replace` route (multipart: old filename + new
  file) calling the Task 1 `_replace`. Reuse the existing delete route for
  *Delete*.
- Frontend: an **Update** action on each document row → file input → calls the
  replace route, optimistic refresh. NLS keys for both labels (web-separate
  catalogue, per `web-i-tech-constraints`).

**Test:** route replaces (old gone from `manifest`, new present); component
renders the Update control and posts the chosen file.

### Task 8 — web per-document *date* field

**Files:** web library viewer, `service/library_web_ops.py` + route; component
test.

- Backend: `PATCH …/library/<file>/date` body `{date: ISO|null}` → `set_doc_date`
  (Task 2). Surface the date in the library status payload.
- Frontend: an inline editable date control per document row, blank by default;
  saving calls the PATCH route.

**Test:** PATCH persists the date into `manifest.json`; clearing sets it back to
`null`; the control shows the stored value.

## Acceptance criteria

- [ ] *Update* on a document archives the old file out of the index and indexes
      the new one in a single action; the old chunks no longer appear in
      retrieval.
- [ ] A document can carry an optional user-set date stored in `manifest.json`;
      blank by default; mtime is never trusted as a date.
- [ ] Every injected RAG chunk shows `[<doc> · <date|undated>]`.
- [ ] When two retrieved sources conflict, the agent prefers the more recent
      dated source and **tells the user they disagree**; undated → flags without
      picking.
- [ ] After an opinion change, the freeze keeps the new stance only (emits
      `CHANGED:`); a workflow run never injects the raw `cache.md`.
- [ ] No "version", "supersede", "status" or "as-of" concept exists anywhere in
      the code or UI.

## Non-goals (deliberately abandoned)

This feature is intentionally **small**. The following are **not built and not
deferred — they are dropped**:

- **No version lineage** — no `doc_id`→version graph, no `supersedes`, no
  per-version rows. Revising a document is a *replace*, full stop.
- **No status lifecycle** (`draft/current/superseded/archived`). A document is
  indexed or it is not.
- **No as-of / time-travel** retrieval. There is no "what did the roadmap say in
  March?" query.
- **No dedicated catalog database** and **no `LibraryCatalog` Protocol**. The
  optional date lives in the existing `manifest.json`.
- **No automatic contradiction detector.** Conflicts are surfaced by the agent
  from the provenance headers and recorded through the existing claims ledger;
  we do not build a new reconciliation engine.
- **No body diff/merge** of PPTX/PDF content.
