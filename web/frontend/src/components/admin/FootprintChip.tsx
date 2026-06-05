"use client";

import { type CSSProperties, type FC } from "react";
import { useTranslation } from "react-i18next";
import { tokens } from "../_shared/armance-tokens";

export interface FootprintChipProps {
  /** Total gCO₂e for the session (null = unknown / no data yet). */
  gco2e: number | null;
  water_ml: number | null;
  /** Lower / upper EcoLogits carbon bounds (optional; renders a range). */
  gco2eMin?: number | null;
  gco2eMax?: number | null;
  /** True when any entry in the session is an estimate (proxy model). */
  hasEstimate: boolean;
  showWater: boolean;
}

const EN_DASH = "–"; // –

function formatCo2(
  gco2e: number,
  gco2eMin: number | null | undefined,
  gco2eMax: number | null | undefined,
): string {
  if (
    gco2eMin != null &&
    gco2eMax != null &&
    Math.abs(gco2eMax - gco2eMin) > 1e-9
  ) {
    return `[${gco2eMin.toFixed(1)} ${EN_DASH} ${gco2eMax.toFixed(1)}]gCO₂e`;
  }
  return `${gco2e.toFixed(1)}gCO₂e`;
}

export const FootprintChip: FC<FootprintChipProps> = ({
  gco2e,
  water_ml,
  gco2eMin,
  gco2eMax,
  hasEstimate,
  showWater,
}) => {
  const { t } = useTranslation();

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
      <div
        data-testid="footprint-chip"
        style={container}
        title={t("admin:footprint.unknown_title")}
      >
        <span>🌱?</span>
      </div>
    );
  }

  const co2 = formatCo2(gco2e, gco2eMin, gco2eMax);
  const isRange =
    gco2eMin != null && gco2eMax != null && Math.abs(gco2eMax - gco2eMin) > 1e-9;

  const badge: CSSProperties = {
    color: tokens.accent,
    fontSize: 11,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: 0.3,
  };

  return (
    <div data-testid="footprint-chip" style={container} title={t("admin:footprint.title")}>
      <span aria-label={isRange ? t("admin:footprint.range_aria") : undefined}>
        {hasEstimate ? "~" : ""}🌱{co2}
      </span>
      {hasEstimate && (
        <span data-testid="footprint-estimate-badge" style={badge}>
          {t("admin:footprint.estimate_badge")}
        </span>
      )}
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
