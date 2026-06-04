"use client";

import { type CSSProperties, type FC } from "react";
import { tokens } from "../_shared/armance-tokens";

export interface FootprintChipProps {
  /** Total gCO₂e for the session (null = unknown / no data yet). */
  gco2e: number | null;
  water_ml: number | null;
  /** True when any entry in the session is an estimate (proxy model). */
  hasEstimate: boolean;
  showWater: boolean;
}

export const FootprintChip: FC<FootprintChipProps> = ({
  gco2e,
  water_ml,
  hasEstimate,
  showWater,
}) => {
  const container: CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: 4,
    color: tokens.inkSoft,
    fontSize: 13,
    fontFamily: tokens.ffMono,
    background: "rgba(107, 79, 138, 0.08)",
    border: `1px solid ${tokens.ruleSoft || "rgba(0,0,0,0.05)"}`,
    padding: "2px 8px",
    borderRadius: 999,
  };

  if (gco2e === null) {
    return (
      <div data-testid="footprint-chip" style={container} title="Empreinte environnementale inconnue">
        <span>🌱?</span>
      </div>
    );
  }

  const formattedCo2 = gco2e.toFixed(1);

  return (
    <div
      data-testid="footprint-chip"
      style={container}
      title="Empreinte environnementale (EcoLogits)"
    >
      <span>
        {hasEstimate ? "~" : ""}🌱{formattedCo2}gCO₂e
      </span>
      {showWater && water_ml !== null && (
        <>
          <span style={{ color: tokens.inkFaint }}>·</span>
          <span>💧{Math.round(water_ml)}mL</span>
        </>
      )}
    </div>
  );
};

export default FootprintChip;
