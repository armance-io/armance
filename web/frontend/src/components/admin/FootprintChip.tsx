/**
 * FootprintChip — skeleton for the live 🌱 gCO₂e chip in the web header.
 *
 * DATA DEPENDENCY: blocked on Epic C (SSE ledger-snapshot channel).
 * The SSE event stream (events.py) does not yet emit ledger snapshots;
 * Epic C must add that channel before this chip can go live.
 *
 * Visual content comes from the Claude Design hand-off.
 * Props mirror the TUI chip: gco2e, estimate, unknown, show_water.
 */
import type { FC } from "react";

export interface FootprintChipProps {
  /** Total gCO₂e for the session (null = unknown / no data yet). */
  gco2e: number | null;
  water_ml: number | null;
  /** True when any entry in the session is an estimate (proxy model). */
  hasEstimate: boolean;
  showWater: boolean;
}

/**
 * FootprintChip renders 🌱{gco2e}gCO₂e (· 💧{water_ml}mL).
 * ~ prefix when hasEstimate; 🌱? when gco2e is null.
 *
 * @skeleton — blocked on Epic C SSE ledger-snapshot; replace `return null`
 * after Epic C ships the live data channel + Design delivers the visual.
 */
export const FootprintChip: FC<FootprintChipProps> = (_props) => {
  // TODO: unblock after Epic C adds ledger-snapshot SSE event
  return null;
};

export default FootprintChip;
