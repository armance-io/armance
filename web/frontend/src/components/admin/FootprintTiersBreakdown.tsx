"use client";

import { type CSSProperties, type FC, useState } from "react";
import { tokens } from "../_shared/armance-tokens";

export interface FootprintTierDetails {
  category: "declared" | "computed" | "estimated" | "bounded";
  model: string;
  proxy_model?: string | null;
  gco2e: number;
  calls: number;
}

export interface FootprintTiersBreakdownProps {
  tiers?: {
    declared: number;
    computed: number;
    estimated: number;
    bounded: number;
  } | undefined;
  details?: FootprintTierDetails[] | undefined;
  t: (key: string) => string;
}

const PALETTE = {
  declared: "hsl(120, 15%, 55%)",  // Sage green
  computed: "var(--accent, #6b4f8a)", // Mona violet
  estimated: "hsl(35, 30%, 60%)",  // Ocre orange
  bounded: "hsl(0, 30%, 65%)",    // Terra cotta red
};

export const FootprintTiersBreakdown: FC<FootprintTiersBreakdownProps> = ({
  tiers,
  details = [],
  t,
}) => {
  const [open, setOpen] = useState(false);

  if (!tiers) return null;

  const total = tiers.declared + tiers.computed + tiers.estimated + tiers.bounded;
  if (total === 0) return null;

  const shares = [
    { key: "declared", val: tiers.declared, label: t("admin:footprint.tier_declared") || "Déclaré", color: PALETTE.declared },
    { key: "computed", val: tiers.computed, label: t("admin:footprint.tier_computed") || "Calculé", color: PALETTE.computed },
    { key: "estimated", val: tiers.estimated, label: t("admin:footprint.tier_estimated") || "Estimé", color: PALETTE.estimated },
    { key: "bounded", val: tiers.bounded, label: t("admin:footprint.tier_bounded") || "Borné", color: PALETTE.bounded },
  ].filter((s) => s.val > 0);

  // If there's only one active tier (100% of consumption)
  const isSingle = shares.length === 1;
  const singleLabel = isSingle && shares[0] ? `100% ${shares[0].label.toLowerCase()}` : "";

  // Pie chart calculation
  let cumulativePercent = 0;
  const slices = shares.map((s) => {
    const percentage = (s.val / total) * 100;
    const offset = cumulativePercent;
    cumulativePercent += percentage;
    return { ...s, percentage, offset };
  });

  const buttonStyle: CSSProperties = {
    background: "transparent",
    border: "none",
    padding: "4px 8px",
    cursor: "pointer",
    fontSize: "11px",
    fontFamily: tokens.ffMono,
    color: tokens.accent,
    textDecoration: "underline",
    display: "inline-flex",
    alignItems: "center",
    gap: "4px",
    marginTop: "4px",
  };

  const containerStyle: CSSProperties = {
    marginTop: "8px",
    padding: "12px",
    background: tokens.bgPaperCard,
    border: `1px solid ${tokens.rule}`,
    borderRadius: "2px", // Combos carrées (DESIGN.md)
    fontFamily: tokens.ffSans,
    fontSize: "12px",
    color: tokens.inkSoft,
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  };

  const explainStyle: CSSProperties = {
    fontSize: "11px",
    lineHeight: "1.4",
    borderTop: `1px solid ${tokens.ruleSoft || "rgba(0,0,0,0.05)"}`,
    paddingTop: "8px",
    marginTop: "4px",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start" }}>
      <button
        type="button"
        style={buttonStyle}
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
      >
        <span>{open ? "▾" : "▸"}</span>
        <span>{open ? (t("admin:footprint.hide_tiers") || "Masquer les détails de précision") : (t("admin:footprint.show_tiers") || "Détails de précision et paliers")}</span>
      </button>

      {open && (
        <div style={containerStyle}>
          {/* Pie Chart or Single info */}
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            {isSingle ? (
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span
                  style={{
                    display: "inline-block",
                    width: "12px",
                    height: "12px",
                    borderRadius: "2px",
                    background: shares[0]?.color || "transparent",
                  }}
                />
                <span style={{ fontWeight: 600, color: tokens.ink }}>{singleLabel}</span>
              </div>
            ) : (
              <div style={{ display: "flex", alignItems: "center", gap: "20px" }}>
                {/* SVG Pie Chart */}
                <svg width="40" height="40" viewBox="0 0 40 40" style={{ transform: "rotate(-90deg)", flexShrink: 0 }}>
                  {slices.map((slice, idx) => (
                    <circle
                      key={idx}
                      cx="20"
                      cy="20"
                      r="15.91549430918954"
                      fill="transparent"
                      stroke={slice.color}
                      strokeWidth="6"
                      strokeDasharray={`${slice.percentage} ${100 - slice.percentage}`}
                      strokeDashoffset={-slice.offset}
                    />
                  ))}
                </svg>

                {/* Legend */}
                <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                  {slices.map((slice, idx) => (
                    <div key={idx} style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "11px" }}>
                      <span
                        style={{
                          display: "inline-block",
                          width: "8px",
                          height: "8px",
                          borderRadius: "1px",
                          background: slice.color,
                        }}
                      />
                      <span style={{ color: tokens.ink }}>
                        {slice.percentage.toFixed(0)}% {slice.label}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Model Usage Details */}
          {details.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "6px", borderTop: `1px solid ${tokens.ruleSoft || "rgba(0,0,0,0.05)"}`, paddingTop: "8px" }}>
              <div style={{ fontFamily: tokens.ffMono, fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.06em", color: tokens.inkFaint }}>
                {t("admin:footprint.models_used") || "Modèles appelés"}
              </div>
              {details.map((d, idx) => {
                const percentage = total > 0 ? ((d.gco2e / total) * 100).toFixed(0) : "0";
                return (
                  <div key={idx} style={{ display: "flex", flexDirection: "column", gap: "2px", paddingLeft: "8px", borderLeft: `2px solid ${PALETTE[d.category]}` }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: "8px" }}>
                      <span style={{ fontWeight: 600, color: tokens.ink, fontFamily: tokens.ffMono, fontSize: "11px" }}>
                        {d.model}
                      </span>
                      <span style={{ fontSize: "10px", fontFamily: tokens.ffMono }}>
                        {percentage}% · {d.gco2e.toFixed(2)} gCO₂e ({d.calls} call{d.calls > 1 ? "s" : ""})
                      </span>
                    </div>
                    {d.category === "declared" && (
                      <span style={{ fontSize: "11px", color: tokens.inkSoft }}>
                        {t("admin:footprint.desc_declared") || "Modèle documenté et validé au registre EcoLogits."}
                      </span>
                    )}
                    {d.category === "computed" && (
                      <span style={{ fontSize: "11px", color: tokens.inkSoft }}>
                        {t("admin:footprint.desc_computed") || "Estimation calculée à partir du nombre de paramètres déclaré."}
                      </span>
                    )}
                    {d.category === "estimated" && (
                      <span style={{ fontSize: "11px", color: tokens.inkSoft }}>
                        {t("admin:footprint.desc_estimated") || "Consommation projetée via un modèle similaire de référence"} {d.proxy_model ? `(${d.proxy_model})` : ""}.
                      </span>
                    )}
                    {d.category === "bounded" && (
                      <span style={{ fontSize: "11px", color: tokens.inkSoft }}>
                        {t("admin:footprint.desc_bounded") || "Consommation inconnue, bornée entre nano (0,1 Wh) et grand MoE (33 Wh)."}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Dynamic Bounding explanation if present */}
          {tiers.bounded > 0 && (
            <div style={explainStyle}>
              <span style={{ fontWeight: 600, color: tokens.ink }}>{t("admin:footprint.bounding_calc_title") || "Calcul du bornage physique :"}</span>{" "}
              {t("admin:footprint.bounding_calc_desc") || "En l'absence de métadonnées, l'empreinte est bornée entre deux extrêmes de la littérature (Jegham et al. 2025) : 0,1 Wh (nano-modèle 1-3B sur H100) et 33 Wh (MoE/dense >400B sur A100), mis à l'échelle selon les jetons de sortie et multipliés par le mix carbone de la zone."}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
