# Workflow live pipeline view + background run

> Status: **proposed, not started**.
> Author: 2026-05-24 user-journey thread.
> Supersedes the Story 3 sketch in [`workflow-runtime-ux.md`](workflow-runtime-ux.md),
> which is kept for Stories 1 + 2.
> Linked bug: [`bugs/sidebar-tasks-dead-section.md`](../bugs/sidebar-tasks-dead-section.md).

## Symptom

When a workflow runs, the TUI shows a generic "thinking" — the user cannot
see which step is executing, which agent is busy, whether the run is
making progress, whether one specialist is stuck. The sidebar has a
"Tasks" section that is permanently empty (dead UI).

In parallel: the workflow run blocks the TUI input bar. The user must
wait until the entire run finishes before chatting with any agent.

## Goal

Three deliverables, in order of independence:

1. **Pipeline view** — sidebar "Tasks" section is repurposed into
   "Active workflow", reading `manifest.json` of the running workflow.
2. **Agent spinner** — each agent currently working a step shows a live
   spinner in the agents pane.
3. **Background workflow** — workflow runs do not block the input bar;
   other agents stay reachable while specialists in the workflow are
   busy. Agents that are currently inside a workflow step are marked
   **busy** and reject new turns until they free.

## Phase 1a — Decommission `/task` + repurpose sidebar

`/task <domain> <prompt>` is dead code (no NL alias, dead UI section,
strictly inferior to `@<agent> <prompt>`). Removing it frees the sidebar
slot.

### Implementation

| File | Action |
|---|---|
| `service/task_ops.py` | drop `cmd_task` (keep the other handlers in the file) |
| `service/handlers.py` | drop import + `HANDLERS["task"]` entry |
| `service/help_text.py` | drop `"task"` from allow-list |
| `service/agents/host_agent.py` | drop the `/task` line from the help block |
| `service/export.py` | drop the `/task` doc line |
| `client/tui/widgets/sidebar.py` | rename section `tasks` → `active_workflow`; drop `_tasks` state, `set_tasks`, `add_task`, `clear_tasks`, `jump_tasks`; keep the binding `3` for the new section |
| `nls_catalogues/{en,fr}.yaml` | remove `task.*` keys + `sidebar.tasks`; add `sidebar.active_workflow` |
| `tests/unit/client/tui/test_tui_loop.py` | drop `test_cmd_task_*` (3 tests) |
| `core/models/task.py` | **keep** — used internally by every workflow step |

~135 LOC net removed.

### Acceptance

- [ ] `/task` returns "unknown command" or is absent from help.
- [ ] Sidebar still has 3 sections; section 3 now reads "Active workflow"
      and is empty until a run starts.
- [ ] All other slash commands still work; the 3 dropped tests are the
      only failing ones in the diff.

## Phase 1b — Pipeline view fed by manifest.json

### Implementation

- `ctx.state.active_workflow_run_path: Path | None` — set by
  `_cmd_workflow_run` when a run starts, cleared when the run completes
  or aborts.
- `client/tui/widgets/active_workflow.py` — new widget. Polls
  `manifest.json` via Textual `set_interval(1.0, refresh)` while the
  run is `status == "running"`.
- Layout per step:
  - `⏳` queued, `🟢` working, `✅` completed, `❌` failed, `⏭` skipped.
  - Step id + role + duration (once `ended_at` is set) + token count.
- Header: workflow name + strategy gem (🟢/🟡/🔴) + global elapsed.
- Footer: last 5 runs from `runs.json` (id, status, duration, tokens,
  cost or `N/A`).

### Acceptance

- [ ] Sidebar refreshes while a run is in progress, no manual reload.
- [ ] Each step transitions `queued → working → completed/failed/skipped`
      visibly.
- [ ] Past-runs footer shows `N/A` for cost when not measured.
- [ ] When no run is active, the section shows the last completed run +
      a hint *« Lancez un workflow via Kim. »*.

## Phase 2 — Agent spinner (only when tokens are flowing)

### Implementation

- Manifest enrichment: `mark_step_started` writes the resolved
  `agent_name` alongside the existing `agent_role` field. (One line in
  `service/workflow_runs.py`; the resolver `_resolve_step_agent` runs in
  handlers and already has the name handy.)
- Sidebar agents pane reads `manifest.steps[*]` for steps with
  `status == "working"` and turns on a spinner badge next to each
  matching agent name.
- **Known limitation — spin only when tokens are consumed.** The current
  spinner ticks for the entire wall-clock duration of a step, including
  the period between `mark_step_started` and the first token returned by
  the provider (network, queueing, provider cold start — sometimes
  several seconds where nothing is happening on the agent side). The
  spinner should only animate while the provider is actively streaming.
  Implementation requires plumbing the existing `on_token` callback in
  `SpecialistRunner` through to the sidebar — currently only used for
  direct-message streaming.

  Tracked as: [`bugs/spinner-spins-without-tokens.md`](../bugs/spinner-spins-without-tokens.md).

### Acceptance

- [ ] An agent currently inside a `kind: task` step is visually marked
      working in the agents pane.
- [ ] The spinner clears within ~1s of step completion / failure.
- [ ] Steps that share an agent (loops, retries) do not double-mark.

## Phase 3 — Workflow background + agent busy

### Design rationale

A full async-background workflow with concurrent chat raises subtle
issues (provider rate limits, HITL race against chat, cancellation
semantics). The simpler model the user asked for:

- The workflow runs in the background — the input bar stays open.
- Specialists currently executing a workflow step are marked **busy**.
- Any user attempt to chat with a busy specialist returns a one-line
  refusal: *« <Name> est en train de travailler sur le workflow `<wf>`,
  étape `<step>`. Elle sera disponible dans un instant. »*
- Meta-agents (Armance, Malik, Kim, Mona, Serge) are **always** reachable.
- HITL checkpoints from a running workflow surface in the chat as a
  system message with the question; the user answers normally; the
  router routes the answer back to the waiting workflow via the existing
  `CheckpointHandler`.

### Implementation

- `_cmd_workflow_run` no longer blocks: wrap the body in
  `asyncio.create_task(...)`, store the handle in
  `ctx.state.background_runs: dict[str, asyncio.Task]`.
- New helper `service/agent_busy.py`:
  - `mark_agent_busy(ctx, agent_name, run_id, step_id)` /
    `mark_agent_free(ctx, agent_name)` — called by `mark_step_started` /
    `mark_step_completed` adapter.
  - `is_agent_busy(ctx, agent_name) -> tuple[bool, str | None]` —
    returns the human-readable explanation.
- `chat_handlers/specialist.py` consults `is_agent_busy` before
  dispatching a turn; on busy, returns the refusal string instead of
  calling `run_specialist`.
- `_cmd_quit` cancels every pending background run cleanly
  (`task.cancel()` + `await asyncio.gather(..., return_exceptions=True)`).
- Token ledger writes already coordinate via the lockfile; no new lock
  needed.

### Out of scope

- Concurrent provider rate limits: documented as a known limit
  ([`bugs/provider-rate-limit-during-background-run.md`](../bugs/provider-rate-limit-during-background-run.md)),
  not handled here. The user accepts the risk.
- Web parity: Phase 3 lands first in the TUI; the web layer follows the
  same pattern when it is built.

### Acceptance

- [ ] Launching a workflow returns to the input bar within 1s, not at
      the end of the run.
- [ ] Chatting with a workflow-busy specialist returns the refusal
      message and does not consume tokens.
- [ ] Chatting with a non-busy specialist or any meta-agent works
      normally.
- [ ] `/quit` cancels in-flight runs without leaving zombie tasks.
- [ ] An HITL question from the running workflow appears in the chat
      and routes the user's reply back to the workflow.

## Dependencies

- ✅ Manifest backbone (`workflow_runs.py` StepRecord + totals).
- ✅ CheckpointHandler protocol (already routes through `ctx`).
- ⏳ This document → implementation on green light.

## Estimate

| Phase | Hours |
|---|---|
| 1a (decommission `/task` + rename section) | 1 |
| 1b (pipeline view) | 3 |
| 2 (agent spinner — without the on_token plumbing) | 2 |
| 3 (background + busy) | 3 |
| **Total** | **~9h** |
