"use client";

import { type FC, useState } from "react";
import { tokens } from "../_shared/armance-tokens";
import { useSessionMetrics } from "@/lib/useSessionMetrics";
import { useRouteParams } from "@/lib/routeParams";

/**
 * Header metrics strip — live tokens + environmental footprint, TUI parity.
 * Always-on, calm, monospace figures. Environmental first (house intent).
 * Hovering the footprint reveals a detail card: range + ADEME equivalences.
 */
function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

const EN_DASH = "–";

export const HeaderMetrics: FC<{ t: (k: string) => string }> = ({ t }) => {
  const { pid } = useRouteParams();
  const m = useSessionMetrics(pid || undefined);
  const [hovered, setHovered] = useState(false);

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
  const hasRange = m.gco2eMax - m.gco2eMin > 1e-9;
  const showDetail = hovered && m.gco2e > 0;

  return (
    <div
      style={{ display: "flex", alignItems: "center", gap: 16, position: "relative" }}
      data-testid="header-metrics"
    >
      {/* Footprint cells share a hover target so the detail card covers both. */}
      <div
        style={{ display: "inline-flex", alignItems: "center", gap: 16 }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        data-testid="header-footprint-hover"
      >
        {cell("🌱", `${est}${m.gco2e.toFixed(1)} gCO₂e`, t("visual:metrics.co2e_aria"), true)}
        {cell("💧", `${est}${Math.round(m.waterMl)} mL`, t("visual:metrics.water_aria"), true)}
      </div>
      <span style={{ width: 1, height: 14, background: tokens.rule }} aria-hidden="true" />
      {cell("↓", fmtTokens(m.tokensIn), t("visual:metrics.tokens_in_aria"))}
      {cell("↑", fmtTokens(m.tokensOut), t("visual:metrics.tokens_out_aria"))}

      {showDetail && (
        <div
          data-testid="footprint-detail"
          role="tooltip"
          style={{
            position: "absolute",
            top: "calc(100% + 8px)",
            left: 0,
            zIndex: 30,
            minWidth: 220,
            padding: "12px 14px",
            background: tokens.bgPaperCard,
            border: `1px solid ${tokens.rule}`,
            borderRadius: 4,
            boxShadow: "0 6px 20px color-mix(in srgb, var(--ink) 14%, transparent)",
            fontFamily: tokens.ffSans,
            fontSize: 12,
            color: tokens.ink,
            lineHeight: 1.5,
          }}
        >
          <div style={{ fontFamily: tokens.ffMono, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", color: tokens.inkSoft, marginBottom: 6 }}>
            {t("visual:metrics.detail_title")}
          </div>
          <div style={{ marginBottom: 4 }}>
            🌱{" "}
            {hasRange
              ? `${est}[${m.gco2eMin.toFixed(2)} ${EN_DASH} ${m.gco2eMax.toFixed(2)}] gCO₂e`
              : `${est}${m.gco2e.toFixed(2)} gCO₂e`}
          </div>
          <div style={{ marginBottom: m.equiv ? 8 : 0 }}>💧 {est}{Math.round(m.waterMl)} mL</div>
          {m.equiv && (
            <div style={{ borderTop: `1px solid ${tokens.ruleSoft || tokens.rule}`, paddingTop: 8, color: tokens.inkSoft, display: "flex", flexDirection: "column", gap: 2 }}>
              <span>≈ {fmtEquiv(m.equiv.phone_charges)} {t("admin:stats.equiv.phone_charges")}</span>
              <span>≈ {fmtEquiv(m.equiv.car_km)} {t("admin:stats.equiv.car_km")}</span>
              <span>≈ {fmtEquiv(m.equiv.water_glasses)} {t("admin:stats.equiv.water_glasses")}</span>
            </div>
          )}
          {m.hasEstimate && (
            <div style={{ marginTop: 8, fontStyle: "italic", color: tokens.inkFaint, fontSize: 11 }}>
              {t("visual:metrics.detail_estimate")}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

function fmtEquiv(n: number): string {
  return n >= 1 ? String(Math.round(n)) : n.toFixed(1);
}

export default HeaderMetrics;
