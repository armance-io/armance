/**
 * Creuset (crucible) stage vocabulary + soft Belle-Époque gem tints.
 *
 * Each crucible stage — draft → critique → synthesis → gate — earns a
 * DISTINCT, muted HSL gem so the sub-graph reads at a glance without ever
 * resorting to saturated primaries or emoji. `standard` steps carry no
 * badge (they are the ordinary flow) and are absent from this map.
 */

export type CrucibleStage =
  | "draft"
  | "critique"
  | "synthesis"
  | "gate"
  | "standard";

export interface StageGem {
  /** i18n key suffix under `workflow:stage.*`. */
  key: CrucibleStage;
  /** Soft gem hue for the badge fill/border. */
  hue: string;
}

/**
 * Soft, distinct gems — slate for the raw drafts, terracotta for the
 * adversarial critique, violet (the house accent) for synthesis, and an
 * ochre "seal" for the gate verdict. All low-saturation, parchment-safe.
 */
export const STAGE_GEMS: Record<
  Exclude<CrucibleStage, "standard">,
  StageGem
> = {
  draft: { key: "draft", hue: "hsl(205, 20%, 52%)" },
  critique: { key: "critique", hue: "hsl(18, 34%, 56%)" },
  synthesis: { key: "synthesis", hue: "var(--accent, #6b4f8a)" },
  gate: { key: "gate", hue: "hsl(42, 36%, 50%)" },
};

export function stageGem(stage: CrucibleStage | null | undefined): StageGem | null {
  if (!stage || stage === "standard") return null;
  return STAGE_GEMS[stage] ?? null;
}

/* ─── Quantity formatters (shared, non-fabricating) ──────────────────────── */

export function fmtDuration(ms?: number | null): string {
  if (ms === undefined || ms === null) return "";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function fmtTokens(n?: number | null): string {
  if (n === undefined || n === null) return "";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

export function fmtCost(c?: number | null): string {
  if (c === undefined || c === null) return "";
  return `$${c.toFixed(4)}`;
}

/**
 * The cost line for a step, following the strict rule: show `cost_usd` when
 * present, else the summed token count, else nothing. NEVER invent a figure.
 */
export function stepCostLabel(
  cost?: number | null,
  tokensIn?: number | null,
  tokensOut?: number | null,
): string {
  if (cost !== undefined && cost !== null) return fmtCost(cost);
  const hasTokens =
    (tokensIn !== undefined && tokensIn !== null) ||
    (tokensOut !== undefined && tokensOut !== null);
  if (hasTokens) return fmtTokens((tokensIn ?? 0) + (tokensOut ?? 0));
  return "";
}
