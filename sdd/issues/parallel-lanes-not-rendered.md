# Parallel workflow steps don't render as concurrent lanes (D11)

> Status: **open, deferred** (recorded 2026-06-10). This is the last
> big visual gap of Web Epic D
> (`../features/web-d-pipeline.md` §D.11 / story D6).
> Blocked by `workflow-runtime-ux` Story 2 (true `asyncio.gather`
> parallelism per DAG level) — without real overlapping
> `started_at`/`ended_at` intervals there is nothing honest to draw.

## Symptom

Two workflow steps that belong to the same DAG level (no dependency
between them) render in a single visual lane in `WorkflowGraph.tsx`,
as if they ran sequentially. The user cannot see that the house
deliberates in parallel — one of the key "wow" moments of the live
run view.

## Cause

1. Backend: the executor still runs DAG levels sequentially
   (`workflow-runtime-ux` Story 2 not built). Steps never actually
   overlap, so the manifest never contains overlapping intervals.
2. Frontend: `lib/graphLayout.ts` has no lane-packing — it lays the
   dagre LR graph out but does not split overlapping intervals into
   visible parallel lanes.

## Fix (when picked up)

Per `web-d-pipeline.md` §D.11:
1. Playwright (red): two steps with overlapping `started_at`/`ended_at`
   render in two visible lanes; sequential steps render in one lane.
2. Implement lane-packing in `graphLayout.ts`.
3. Requires `workflow-runtime-ux` Story 2 first for live runs (past
   manifests with overlapping intervals can be used for the test
   fixture meanwhile).

## Acceptance

- [ ] Overlapping steps → two lanes; sequential steps → one lane.
- [ ] Live run shows the lanes while both steps are `working`.
