# Workflow runtime UX — proposal

> Status: **partially landed**.
> 2026-05-18: manifest enrichi + pre-run health-check.
> 2026-05-18 (later): Story 1 (workflow.scope + default prompt builder)
>   + run mode tag `[EXECUTE:/workflow-run:<name>:<interactive|autonomous>]`
>   with Mona as proxy in autonomous mode.
> Remaining: Story 2 (parallelism — already partially in place via
> `asyncio.gather` per level) and Story 3 (pipeline view).

## Scope

Three independent stories surfaced during user testing of the workflow
runtime. They cluster around the run lifecycle: better prompts for staff
agents, parallel execution where the DAG allows it, and a CI/CD-style
pipeline view of runs.

---

## Story 1 — Staff prompt scope (Mona / Serge)

### Symptom

When a workflow runs on a narrow topic (e.g. "build a historical
dossier"), Mona's synthesis still references the broader project
(budget, logistics, comms) and Serge critiques angles outside the
workflow's actual scope. Both staff agents over-reach.

### Cause

Mona and Serge receive the project brief in their context, but no
explicit instruction that *this workflow's scope is narrower than the
project*. They default to commenting on the whole project.

### Fix sketch (~2h)

- New `workflow.scope` field in the workflow YAML (one-line, written
  by Kim when she designs the workflow).
- The runner injects this scope into Mona's and Serge's system_addon
  for the duration of the run. The addon says: *"This workflow's scope
  is ‹scope›. Stay within it. The project brief is background context,
  not the topic of your synthesis / critique."*
- DesignWorkflowSkill validator accepts the optional `scope:` field
  and writes it to the YAML.
- Kim's prompt grows a one-line instruction: *"When the user agrees
  on a workflow, include `scope: <one-line narrow summary>` in the
  YAML."*

### Acceptance

- [ ] Workflow YAML with `scope:` round-trips through load_workflow.
- [ ] Mona's reply in a `kind: judge` step quotes the scope, not the
      project brief.
- [ ] Serge's reply in a `kind: critique` step questions the steps'
      outputs, not the broader project.

---

## Story 2 — Parallel step execution

### Symptom

Two historians (Élise + Théo) doing independent research run
sequentially. Each waits ~30s for the previous. Total: 60s instead of
30s.

### Cause

`execute_workflow` walks the DAG by topological dependency, but
processes ready steps one at a time. The DAG has no concurrency
semantics.

### Fix sketch (~3h)

- `armance/core/models/workflow.py::execute_workflow`: change the inner
  loop to launch all *ready* (dependencies satisfied) steps with
  `asyncio.gather` instead of `await` one-by-one.
- Two failure modes need handling:
  - One step fails while siblings are still running → the existing
    `_run_aborted` flag short-circuits the next wave. In-flight
    siblings finish and persist normally.
  - Mark `step.parallel_group: <name>` (optional) in YAML to opt out
    of parallelism for a step group (useful when the user wants
    deterministic ordering).
- Manifest already supports `started_at` / `ended_at` per step, so the
  pipeline view shows real durations regardless of concurrency.
- Cost / token totals already aggregate correctly.

### Acceptance

- [ ] Two `task` steps with `depends_on: []` run concurrently.
- [ ] Total `duration_ms` ≈ max(step_durations) when steps are
      independent, not sum.
- [ ] No deadlock when a step has multiple dependencies.
- [ ] Failure in one parallel branch still marks the other as
      `completed` if it finished before the abort.

---

## Story 3 — Pipeline view (TUI + future web)

### Symptom

Users want to see, while a workflow runs:
- which step is currently `working`,
- which steps are done with a green check / red cross,
- per-step duration and token count,
- a historical list of runs with status, duration, cost (or "N/A"),
- agent spinners synced with the step they're in.

This mirrors a GitLab / GitHub Actions pipeline view.

### Foundation already landed

The manifest schema rewritten today (`workflow_runs.py` StepRecord +
totals + cost-never-estimated) is the data backbone. Both TUI and the
future web layer read the same JSON.

### TUI plan (~3h, minimal)

- Sidebar pane `[Active workflow]`:
  - Workflow name + strategy gem.
  - Step list with status emoji (⏳ queued / 🟢 working / ✅ completed
    / ❌ failed / ⏭ skipped) and duration once known.
  - Live polling: re-read the manifest every ~1s while a run is in
    progress. (No WebSocket; the manifest writes happen via
    mark_step_*, the UI just polls the JSON on disk.)
- Sidebar pane `[Past runs]`:
  - Last 5 runs (run_id, status, duration, tokens, cost or "N/A").
- Spinner state on each agent in the agents pane is computed from
  `manifest.steps[*].status == "working"` cross-referenced with
  `_resolve_step_agent(step.role)`.

### Web plan (deferred — lives with the rest of P2.a)

- Read endpoint: `GET /workflows/<name>/runs` → list of compact run
  entries (same shape as `runs.json`).
- Read endpoint: `GET /workflows/<name>/runs/<run_id>` → full manifest.
- Read endpoint: `GET /workflows/<name>/runs/<run_id>/step/<id>` →
  step output markdown.
- No write endpoints from the web; design + launch stays driven by
  Kim in the chat. The web is a viewer.

### Acceptance

- [ ] TUI sidebar refreshes while a run is in progress, no manual
      reload needed.
- [ ] Each step transitions queued → working → completed/failed/skipped
      visibly.
- [ ] Past-runs list shows N/A for cost when tokens were measured but
      cost wasn't.
- [ ] Web endpoints return JSON that mirrors `manifest.json` 1:1.

---

## Dependencies

- ✅ Manifest enrichi (this commit).
- ✅ Pre-run health-check (this commit).
- ⏳ Story 1 (staff scope) — independent, can land first.
- ⏳ Story 2 (parallel) — independent.
- ⏳ Story 3 (pipeline view) — depends on having Story 1 + 2 stable to
  avoid building UI on a moving foundation, but TUI sidebar polling
  alone can ship early.

## Out of scope

- WebSocket / SSE push for the web view. Polling is fine at V2.
- Multi-tenant run isolation. V3.
- Persistent cost ledger across runs. V3 (the per-run manifest is
  sufficient until then).
