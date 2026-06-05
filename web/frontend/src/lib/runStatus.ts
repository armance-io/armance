/**
 * Canonical workflow-run status, mirroring the backend run manifest
 * (service/workflow_runs.py): queued | working | completed | failed | skipped |
 * unknown. The frontend live graph also uses running/cancelled aliases.
 *
 * Single source so every run component (history, node, detail, delete,
 * interrupt) agrees — a status the UI doesn't know must never crash a render.
 */
export type RunStatus =
  | "queued"
  | "working"
  | "running"
  | "completed"
  | "failed"
  | "skipped"
  | "cancelled"
  | "unknown";
