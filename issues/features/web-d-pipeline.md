# Web Epic D · The pipeline view (workflow runtime)

> Status: **partial — backend depends on `workflow-runtime-ux` Story 2
> for true parallelism + on `workflow-live-pipeline` for the agent
> spinner**.
> Part of [`web-layer-stories.md`](web-layer-stories.md).

## Goal

Browser counterpart of the TUI pipeline view. The TUI sidebar and the
web view read the **same `manifest.json`**. Steps move queued → working →
done with live durations and per-step token counts; independent steps
show concurrent run windows; the user picks run depth in plain words
before launch.

## User stories covered

- **D1** — Watch a workflow run live (step list, durations, agent
  spinners).
- **D2** — See the panel deliberate in parallel (concurrent lanes).
- **D3** — Choose run depth + mode (interactive / autonomous) in
  friendly language before launch.

## Backend dependencies

| Dependency | Status |
|---|---|
| Manifest schema (`StepRecord`, totals) in `workflow_runs.py` | ✅ |
| Cost-never-estimated handling | ✅ |
| `pre_run_hook` / `post_run_hook` | ✅ |
| Parallel `asyncio.gather` per DAG level | ⚠ partial — see [`workflow-runtime-ux.md`](workflow-runtime-ux.md) Story 2 |
| Agent spinner data (`agent_name` in manifest) | ⏳ → ships with [`workflow-live-pipeline.md`](workflow-live-pipeline.md) Phase 2 |
| Background runs with agent-busy | ⏳ → ships with [`workflow-live-pipeline.md`](workflow-live-pipeline.md) Phase 3 |

The web pipeline view reads the same data structures the TUI view reads.
Anything that ships in `workflow-live-pipeline.md` lands in both at the
same time; the web view is the second consumer of the same JSON.

## File / module layout

```
web/backend/routes/
  active_workflow.py   GET /sessions/{sid}/active-workflow
                       (resolves to the live manifest, or null)

web/frontend/app/session/[id]/
  pipeline/
    PipelineView.tsx      step lanes, parallel rendering
    StepCard.tsx          status emoji, duration, tokens
    AgentSpinner.tsx      consumes the `agent_streaming` event (Phase 2)
    DepthPicker.tsx       friendly D3 wording → mode mapping
```

## TDD task list

### Task D.1 — `GET /active-workflow` route
1. Backend test (red): when no run is in progress, the route returns
   200 `{"active": null}`. When a run is in progress, it returns
   `{"active": {"workflow": "<name>", "run_id": "<id>",
   "manifest_path": "..."}}`.
2. Implement using `ctx.state.active_workflow_run_path` (the same field
   the TUI sidebar will consume — see
   [`workflow-live-pipeline.md`](workflow-live-pipeline.md) Phase 1b).

### Task D.2 — Pipeline frontend reads the manifest
1. Frontend test (red): on `/session/<sid>`, with a running workflow,
   the pipeline view renders one card per step with the expected
   status emoji.
2. Implement: poll `GET /active-workflow` every 1 s; when a run id
   appears, poll `GET /workflows/<name>/runs/<run_id>` every 1 s for
   the manifest; render `StepCard`s.

### Task D.3 — Parallel lanes
1. Frontend test (red): two steps with overlapping
   `started_at`..`ended_at` ranges render in two visible lanes; one step
   with non-overlapping range renders sequentially.
2. Implement a lane-packing algorithm that buckets steps by overlap.
3. Backend dependency: `workflow-runtime-ux.md` Story 2 (full
   parallel exec). Until it lands, the test still passes on
   sequential-only manifests; D2 acceptance is gated on Story 2.

### Task D.4 — Agent spinner (event-driven)
1. Backend test (red): when `mark_step_started` fires, the bus emits
   `agent_streaming_started` with `{agent_name, step_id}`; when the
   underlying `on_token` callback fires, `agent_streaming` events are
   throttled at ~1 per 500 ms; when the step completes,
   `agent_streaming_end` fires.
2. Implement the emitters in `service/workflow_runs.py` and in
   `SpecialistRunner.on_token`. (This is the same plumbing
   [`workflow-live-pipeline.md`](workflow-live-pipeline.md) Phase 2
   uses; the bug
   [`bugs/spinner-spins-without-tokens.md`](../bugs/spinner-spins-without-tokens.md)
   tracks the *« spinner without tokens »* issue.)
3. Frontend test (red): `AgentSpinner` ticks while `agent_streaming`
   events arrive within the last 1.5 s; freezes otherwise.
4. Implement.

### Task D.5 — Depth + mode picker (D3)
1. Frontend test (red): the pre-launch panel offers two choices in
   plain words — *« un avis rapide »* / *« une analyse approfondie,
   challengée »* — mapped to the existing strategy gem and to
   `interactive` / `autonomous` mode. Submitting issues the
   `[EXECUTE:/workflow-run:<name>:<mode>]` slash via the chat dispatch
   (no new tag, no new code path).
2. Implement.

### Task D.6 — Coverage gate
1. Coverage on `web/backend/routes/active_workflow.py` ≥ 90 %.
2. Frontend coverage on `PipelineView.tsx` ≥ 80 %.

## Acceptance criteria (epic-level)

- [ ] Step transitions are visible in the browser without reload.
- [ ] Independent steps show overlapping run windows once
      `workflow-runtime-ux.md` Story 2 lands.
- [ ] The agent spinner is honest about provider latency (Phase 2
      semantics from `workflow-live-pipeline.md`).
- [ ] The pre-launch picker is non-technical and correctly drives the
      run mode.
- [ ] No `src/armance/` changes that are not already required by
      `workflow-live-pipeline.md`.

## Out of scope

- Pause / resume of an in-progress workflow (V3).
- Per-step retry from the browser (V3).
