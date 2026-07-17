/**
 * Step status palette — soft Belle-Époque gems per DESIGN.md §2.
 * Split from StepNode.tsx to keep the component under the 250-LOC cap.
 */

export type StepStatus =
  | "queued"
  | "working"
  | "completed"
  | "failed"
  | "cancelled"
  | "skipped"
  | "provided";

export const STATUS_DOT_COLOR: Record<StepStatus, string> = {
  queued: "var(--ink-faint, #9c8e7e)",
  working: "hsl(35, 30%, 60%)",
  completed: "hsl(120, 15%, 55%)",
  failed: "hsl(0, 30%, 65%)",
  cancelled: "var(--ink-faint, #9c8e7e)",
  skipped: "var(--ink-faint, #9c8e7e)",
  provided: "var(--accent, #6b4f8a)",
};

// Soft, muted backgrounds per DESIGN.md gems.
export const STATUS_BG: Record<StepStatus, string> = {
  queued: "var(--bg-paper, #f4ede0)",
  working: "color-mix(in srgb, hsl(35, 30%, 60%) 12%, var(--bg-paper, #f4ede0))",
  completed: "color-mix(in srgb, hsl(120, 15%, 55%) 14%, var(--bg-paper, #f4ede0))",
  failed: "color-mix(in srgb, hsl(0, 30%, 65%) 12%, var(--bg-paper, #f4ede0))",
  cancelled: "var(--bg-paper, #f4ede0)",
  skipped: "var(--bg-paper, #f4ede0)",
  provided: "color-mix(in srgb, var(--accent, #6b4f8a) 8%, var(--bg-paper, #f4ede0))",
};
