# Sidebar `Tasks` section is dead UI

> Status: **known, planned for removal**.
> Resolves with [`features/workflow-live-pipeline.md`](../features/workflow-live-pipeline.md) Phase 1a.

## Symptom

`client/tui/widgets/sidebar.py` has a "Tasks" section (binding `3`,
`section-tasks`, `set_tasks` / `add_task` / `clear_tasks` /
`jump_tasks`). Nothing ever populates it in production. The section is
empty for every user, every session.

## Cause

The companion handler `/task <domain> <prompt>` (in
`service/task_ops.py`) was retained from an earlier design where
single-shot agent invocations were a first-class concept. It is now
strictly inferior to:

- `@<agent> <prompt>` (chat with a specialist — has history, streaming,
  proper UI surface in the DM view);
- `/workflow run rapide` (a 1-role × 2-specialist deliberation when the
  user wants a quick answer rather than a chat).

`/task` has **no NL alias** (violating `CLAUDE.md` rule for slash
commands), no test beyond a smoke test, and a UI surface (`sidebar
Tasks`) that nothing calls.

## Fix

Decommission `/task` and repurpose the sidebar section into "Active
workflow" — see [`features/workflow-live-pipeline.md`](../features/workflow-live-pipeline.md)
Phase 1a for the change list.

## Notes for future agents

`core/models/task.py` stays — `Task` is the internal wrapper passed to
`run_specialist` from every workflow step. Only the user-facing slash
command and the dead UI section are dropped.
