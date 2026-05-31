"use client";

import { type CSSProperties, type FC, useState } from "react";
import { tokens } from "../_shared/armance-tokens";
import { displayAgentName } from "@/lib/agentNames";
import type { FootprintResponse } from "../../lib/footprint";

export interface FootprintTabProps {
  data: FootprintResponse | null;
  loading: boolean;
  error: Error | null;
  zone?: string;
  t: (key: string, opts?: Record<string, unknown>) => string;
}

const ZONE_LABELS: Record<string, string> = {
  WOR: "admin:footprint.zone.wor",
};

export const FootprintTab: FC<FootprintTabProps> = ({
  data,
  loading,
  error,
  zone = "WOR",
  t,
}) => {
  // BUG-05.4: method block collapsed by default.
  const [methodOpen, setMethodOpen] = useState(false);

  const container: CSSProperties = {
    fontFamily: tokens.ffSans, color: tokens.ink,
    display: "flex", flexDirection: "column", gap: 24,
  };
  const titleStyle: CSSProperties = {
    fontFamily: tokens.ffSerif, fontSize: 24, fontWeight: 600, color: tokens.ink, margin: 0,
  };
  const table: CSSProperties = { width: "100%", borderCollapse: "collapse", marginTop: 12 };
  const th: CSSProperties = {
    textAlign: "left", padding: "10px 12px", borderBottom: `1px solid ${tokens.rule}`,
    color: tokens.inkSoft, fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em",
  };
  const td: CSSProperties = {
    padding: "12px", borderBottom: `1px solid ${tokens.ruleSoft}`, fontSize: 13,
  };
  const badge: CSSProperties = {
    display: "inline-block", padding: "2px 6px", borderRadius: tokens.radiusSm,
    fontSize: 10, fontFamily: tokens.ffMono, background: "rgba(214, 200, 173, 0.3)", color: tokens.accent,
  };
  const expandBtn: CSSProperties = {
    alignSelf: "flex-start", background: "transparent", border: `1px solid ${tokens.rule}`,
    padding: "8px 16px", borderRadius: tokens.radiusSm, cursor: "pointer", fontSize: 13,
    fontWeight: 500, color: tokens.inkSoft, display: "flex", alignItems: "center", gap: 8,
  };
  const panel: CSSProperties = {
    padding: 16, background: tokens.bgPaperCard, border: `1px solid ${tokens.rule}`,
    borderRadius: tokens.radiusMd, fontSize: 13, color: tokens.inkSoft, lineHeight: 1.6,
  };

  if (loading) return <div style={{ color: tokens.inkSoft }}>{t("app:loading")}</div>;
  if (error) return <div style={{ color: tokens.accent }}>{t("admin:footprint.error")}</div>;
  if (!data) return null;

  const agents = Object.entries(data.by_agent);
  // BUG-05.3: distinguish "real zero data" from "no data at all".
  const hasData = agents.length > 0 && agents.some(([, b]) => b.calls > 0);
  const zoneLabel = t(ZONE_LABELS[zone] ?? "admin:footprint.zone.unknown");

  return (
    <div style={container} data-testid="footprint-tab">
      <h3 style={titleStyle}>🌱 {t("admin:tabs.empreinte")}</h3>

      {!hasData ? (
        <div style={{ color: tokens.inkSoft, fontStyle: "italic" }}>
          {t("admin:footprint.no_data")}
        </div>
      ) : (
        <table style={table}>
          <thead>
            <tr>
              <th style={th}>{t("admin:footprint.col.agent")}</th>
              <th style={th}>{t("admin:footprint.col.calls")}</th>
              <th style={th}>{t("admin:footprint.col.co2e")}</th>
              <th style={th}>{t("admin:footprint.col.water")}</th>
              <th style={th}>{t("admin:footprint.col.type")}</th>
            </tr>
          </thead>
          <tbody>
            {agents.map(([name, bucket]) => (
              <tr key={name}>
                <td style={{ ...td, fontWeight: 500 }}>{displayAgentName(name)}</td>
                <td style={td}>{bucket.calls}</td>
                <td style={td}>
                  {bucket.calls === 0 ? "—" : `${bucket.has_estimate ? "~" : ""}${bucket.gco2e.toFixed(1)} gCO₂e`}
                </td>
                <td style={td}>{bucket.calls === 0 ? "—" : `${Math.round(bucket.water_ml)} mL`}</td>
                <td style={td}>
                  {bucket.has_estimate ? (
                    <span data-testid="estimate-badge" style={badge}>
                      {t("admin:footprint.estimate")}
                    </span>
                  ) : (
                    <span style={{ ...badge, background: "rgba(107, 79, 138, 0.1)" }}>
                      {t("admin:footprint.measured")}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <button
        type="button"
        style={expandBtn}
        onClick={() => setMethodOpen(!methodOpen)}
        aria-expanded={methodOpen}
      >
        <span aria-hidden="true">{methodOpen ? "▾" : "▸"}</span>
        <span>{t("admin:footprint.method")}</span>
      </button>

      {methodOpen && (
        <div style={panel} data-testid="methode-panel">
          <p style={{ margin: 0 }}>{t("admin:footprint.method_body")}</p>
          <p style={{ margin: "12px 0 0 0", fontSize: 12, fontFamily: tokens.ffMono }}
             title={zoneLabel}>
            {t("admin:footprint.zone_label")}: <strong>{zone}</strong> — {zoneLabel}
          </p>
        </div>
      )}
    </div>
  );
};

export default FootprintTab;
