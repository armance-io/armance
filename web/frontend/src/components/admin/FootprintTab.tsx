/**
 * FootprintTab — skeleton component for the admin "Empreinte" tab.
 *
 * Visual content (table, sparklines, estimate badge, Méthode expander)
 * comes from the Claude Design hand-off (web-v2-claude-design-prompts.md).
 * Wire the generated component in place of `return null` below.
 *
 * All i18n strings live in locales/{en,fr}/footprint.json (EI.9).
 */
import type { FC } from "react";
import type { FootprintResponse } from "../../lib/footprint";

export interface FootprintTabProps {
  /** Full rollup from GET /admin/footprint */
  data: FootprintResponse | null;
  loading: boolean;
  error: Error | null;
  /** ISO 3166-1 alpha-3 zone from config (shown in Méthode expander) */
  zone?: string;
  /** i18n translation function */
  t: (key: string, opts?: Record<string, unknown>) => string;
}

/**
 * FootprintTab renders per-agent gCO₂e / mL H₂O totals, a by-day/month
 * sparkline, an estimate badge for ~ rows, and a "Méthode" provenance
 * expander citing EcoLogits + ISO 14044.
 *
 * @skeleton — replace `return null` with the Design-generated component.
 */
export const FootprintTab: FC<FootprintTabProps> = (_props) => {
  // TODO: replace with generated visual from web-v2-claude-design-prompts.md
  return null;
};

export default FootprintTab;
