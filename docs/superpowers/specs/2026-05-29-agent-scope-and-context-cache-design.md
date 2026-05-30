# Agent scope boundaries + context cache — design

Date: 2026-05-29
Branch: `fix/convergence-0.1.1`
Source incident: `tmp/runtime/conversations/f3904b57203c.md`

> No users in production yet. **No migration, no back-compat, no backport.**
> New artifacts are canonical from first run.

## Problem

Two prod problems, in priority order.

### P1 — Cross-agent scope leak (bug)

All agents share one conversation log. Switching from Malik (recruiter,
mid model-fixing chatter) to a specialist carried the recruitment /
broken-model context into the specialist. Observed in the incident log:

- **Samir** (communicant) asked to "present yourself" → dumped the entire
  crew roster + per-agent model assignments. That is Malik's domain, not
  his.
- **Mateo** (climate-scientist) inherited the broken-model-ID thread and
  fixated on it instead of answering.

**Root cause.** The two history filters both use the same leaky gate:

```python
# service/chat_handlers/specialist.py
if t.role == "user" or (t.agent or "") not in _COORD_AGENTS
# service/chat_handlers/malik.py:_filter_history
if turn.role == "user" or norm in _MALIK_AGENTS or turn.agent == agent_name
```

The `turn.role == "user"` clause passes **every** user turn unconditionally.
User turns are already tagged with `agent=` (e.g. a `user→Malik` turn is
tagged `agent="system-hr"`), but that tag is never used to gate visibility.
So recruitment-directed user turns leak into every specialist.

### P2 — Context capture is all-or-nothing (feature)

`host_agent._buffer` silently accumulates substantive turns; `freeze()` is
unconditional and produces a new `L0_v<N>.md` only when explicitly called.
Result: Armance "waits for the scope to be absolutely complete" before
saving — either too few versions (info lost) or, if freezing per fact,
version spam. The buffer is also invisible: it is never shown to the user
and never shared into specialist context.

## Goals

1. Strict competence boundaries: each agent sees only turns in its scope +
   shared project framing. Malik = recruitment only; specialists = their own
   dialogue + the project brief.
2. A visible, shared, crash-durable **context cache** that Armance fills
   incrementally and promotes to a frozen L0 version on user confirmation —
   no version spam, no lost info.
3. **Do not break the workflow execution path.** Kim-orchestrated specialists
   must keep their step-scoped goal *and* shared project context.

## Non-goals (YAGNI)

- No diff/merge-based cache (rejected approach C).
- No multi-writer cache; only Armance writes.
- No migration of the legacy `host_buffer` (no users).

---

## P1 design — `service/agent_visibility.py`

Single source of truth for "which past turns may agent X see in a DM/chat
turn". Replaces the two ad-hoc filters.

### Rule

A turn `t` is visible to agent `X` iff **either**:

- `t.agent == X` (the turn was authored by or directed at X), **or**
- `t.agent` is in the **framing channel** — `{"system-context"}` (Armance).
  Framing is project-level context everyone inherits.

The unconditional `role == "user"` pass is **removed**. A `user→Malik` turn
(`agent="system-hr"`) is no longer visible to Samir.

### Competence map

| Viewer | Sees (history) | Plus (system prompt) |
|---|---|---|
| Specialist | own dm turns + framing | L0 + L1[role] + (L2[theme]) + RAG + **cache** |
| Malik | own turns + framing + `_MALIK_AGENTS` set | roster |
| Kim | own turns + framing + roster turns | roster |
| Mona | own turns + framing | run artefacts |
| Armance | everything (owner/coordinator) | L0 + cache + buffer |

`_MALIK_AGENTS` (existing) is preserved so Malik retains recruitment-relevant
cross-talk. The module exposes one function:

```python
def visible_turns(turns: list[Turn], viewer: str) -> list[dict[str, str]]:
    """Filter conversation turns to those in `viewer`'s competence scope."""
```

`malik.py:_filter_history` and `specialist.py:cmd_chat` both call it; their
inline filters are deleted.

### Why this is safe for workflows

The workflow path (`handlers.py` ~line 450) calls `run_specialist` **without
a `history` argument**. Workflow specialists receive context purely through
the injected system prompt (`--- Context ---`: L0 + L1[role] + L2[theme] +
RAG) plus the step `task.prompt` (the step-specific goal). `agent_visibility`
gates only the DM/chat `history` list, so the workflow path is untouched.
Kim-orchestrated specialists keep step goal (prompt) + shared project context
(L0 + cache in prompt).

---

## P2 design — context cache layer

### Artifact

`.armance/context/cache.md` — first-class, on-disk, beside `L0_v<N>.md`.
Crash-durable. Session metadata keeps a mirror (`cache`) for the resume
picker only; `cache.md` is canonical.

### Shared brief = L0 + cache

Cache is injected everywhere L0 is injected today:

- Host agents (Armance / Malik / Kim / Mona): appended to their loaded L0.
- Specialists (chat **and** workflow): appended in
  `SpecialistRunner._build_layered_context`, right after L0/L1/L2. This is
  why workflow specialists get the cache for free, no history needed.

### Writer — Armance only

Armance replaces today's silent `_buffer.append` with an explicit
cache write when she judges information worth keeping. All other agents read
the cache; none may mutate it (single owner → no write races, clear scope).

### Fullness → propose → freeze

Trigger: cache content crosses **~1500 chars** OR Armance judges a coherent
milestone reached → she emits a **recap** of what would be added and proposes
`/save`.

- User confirms → existing `[EXECUTE:/save]` freeze fires: LLM-compiles
  `prev L0 + cache` → new `L0_v<N+1>.md`; **cache.md cleared**.
- No confirm → cache keeps accumulating (no version spam).

### Ctrl+Q gate

Existing path (`client/tui/screens/main.py:393`) already reads the buffer and
prompts save-or-discard. Rewire to read `cache.md`:

- cache non-empty → Armance recap + "save to context, or dismiss (keep last
  L0 version)?".
- Save → quick-freeze bump (`ContextService.append_quick_freeze`, reading
  cache).
- Dismiss → drop cache, keep last L0.
- Empty cache → quit silently (unchanged).

---

## Components touched

| File | Change |
|---|---|
| `service/agent_visibility.py` | **new** — `visible_turns(turns, viewer)` policy |
| `service/chat_handlers/specialist.py` | call `visible_turns`; delete inline filter |
| `service/chat_handlers/malik.py` | call `visible_turns`; delete `_filter_history` |
| `service/context_service.py` | cache read/write/clear; cache-aware `append_quick_freeze` |
| `service/agents/host_agent.py` | `_buffer` → cache writes; fullness check + recap proposal; inject cache for Armance |
| `service/agents/specialist_runner.py` | inject cache in `_build_layered_context` |
| `client/tui/screens/main.py` | Ctrl+Q gate reads cache.md |
| `storage/paths.py` | canonical `cache.md` path |

## Data flow

```
Armance turn → judges worth-saving → ContextService.cache_append(note)
            → cache.md grows
            → fullness(>=1500 chars) OR milestone → Armance recap + propose /save
user "ok"  → [EXECUTE:/save] → freeze(prev L0 + cache) → L0_v(N+1) → cache cleared
Ctrl+Q     → cache non-empty → recap → save (quick-freeze) | dismiss (drop cache)

Any agent prompt assembly:
  system = ... + L0_body + cache_body + (L1/L2/RAG for specialists)
Specialist DM history = visible_turns(conversation.turns, viewer)
Specialist workflow   = NO history; context via system prompt only (unchanged)
```

## Error handling

- `cache.md` missing/unreadable → treat as empty; log debug; never crash a turn.
- Cache write failure → log, keep in-memory mirror, retry on next save; never
  block the user reply.
- Freeze failure with non-empty cache → cache is NOT cleared (no data loss).

## Testing

- `visible_turns`: user→Malik turn invisible to a specialist; framing turn
  visible to all; own dm turn visible; Malik keeps `_MALIK_AGENTS` cross-talk.
- Regression: replay the incident — specialist asked to present itself does
  not see "change <name> model" turns.
- Cache: append / read / clear; `cache.md` canonical; session mirror updates.
- Injection: cache body appears in both a specialist prompt and a host prompt.
- Workflow: a workflow run still injects L0 + cache via system prompt with no
  `history` arg (path unchanged).
- Fullness: crossing ~1500 chars surfaces a save proposal; confirm bumps L0
  and clears cache; decline keeps accumulating.
- Ctrl+Q: non-empty cache → save branch (quick-freeze) and dismiss branch
  (drop, keep last L0) both covered; empty cache quits silently.

## Open invariants honoured

- No upper-layer imports in `core/` or `service/`.
- New side effect (`/save` driving cache→L0) already uses the `[EXECUTE:/...]`
  tag; no new implicit code path.
- Files ≤ ~300 lines; `agent_visibility.py` is small and new.
