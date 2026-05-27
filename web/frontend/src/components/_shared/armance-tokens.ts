/**
 * Maps component-side token names to CSS variables defined in app/globals.css.
 * Components consume `tokens.<name>` so the same JS surface drives light + dark
 * themes via the `data-theme` attribute on `<html>`.
 */
export const tokens = {
  bgPaper: "var(--bg-paper)",
  bgPaperDeep: "var(--bg-paper-deep)",
  bgPaperCard: "var(--bg-paper-card)",
  ink: "var(--ink)",
  inkSoft: "var(--ink-soft)",
  inkFaint: "var(--ink-faint)",
  rule: "var(--rule)",
  ruleSoft: "var(--rule-soft)",
  accent: "var(--accent)",
  accentSoft: "var(--accent-soft)",
  accentDeep: "var(--accent-deep)",
  danger: "var(--danger)",
  warning: "var(--warning)",
  ffSerif: "var(--ff-serif)",
  ffSans: "var(--ff-sans)",
  ffMono: "var(--ff-mono)",
} as const;

export type Tokens = typeof tokens;
