"use client";

import { type FC } from "react";
import { tokens } from "../_shared/armance-tokens";
import { useSessionMetrics } from "@/lib/useSessionMetrics";
import { useRouteParams } from "@/lib/routeParams";

/**
 * Header metrics strip — live tokens + environmental footprint, TUI parity.
 * Always-on, calm, monospace figures. Environmental first (house intent).
 */
function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

export const HeaderMetrics: FC<{ t: (k: string) => string }> = ({ t }) => {
  const { pid } = useRouteParams();
  const m = useSessionMetrics(pid || undefined);

  const cell = (glyph: string, value: string, label: string, accent = false) => (
    <span
      title={label}
      style={{
        display: "inline-flex",
        alignItems: "baseline",
        gap: 5,
        fontFamily: tokens.ffMono,
        fontSize: 11,
        color: accent ? tokens.accent : tokens.inkSoft,
        whiteSpace: "nowrap",
      }}
    >
      <span aria-hidden="true" style={{ fontSize: 12 }}>{glyph}</span>
      <span style={{ color: tokens.ink }}>{value}</span>
    </span>
  );

  const est = m.hasEstimate ? "~" : "";

  return (
    <div
      style={{ display: "flex", alignItems: "center", gap: 16 }}
      data-testid="header-metrics"
    >
      {cell("🌱", `${est}${m.gco2e.toFixed(1)} gCO₂e`, t("visual:metrics.co2e_aria"), true)}
      {cell("💧", `${est}${Math.round(m.waterMl)} mL`, t("visual:metrics.water_aria"), true)}
      <span style={{ width: 1, height: 14, background: tokens.rule }} aria-hidden="true" />
      {cell("↓", fmtTokens(m.tokensIn), t("visual:metrics.tokens_in_aria"))}
      {cell("↑", fmtTokens(m.tokensOut), t("visual:metrics.tokens_out_aria"))}
    </div>
  );
};

export default HeaderMetrics;
