"use client";

import { type CSSProperties, type FC, useState } from "react";
import { tokens } from "../_shared/armance-tokens";
import type { FootprintResponse } from "../../lib/footprint";

export interface FootprintTabProps {
  data: FootprintResponse | null;
  loading: boolean;
  error: Error | null;
  zone?: string;
  t: (key: string, opts?: Record<string, unknown>) => string;
}

export const FootprintTab: FC<FootprintTabProps> = ({
  data,
  loading,
  error,
  zone = "WOR",
  t,
}) => {
  const [methodOpen, setMethodOpen] = useState(false);

  const container: CSSProperties = {
    fontFamily: tokens.ffSans,
    color: tokens.ink,
    display: "flex",
    flexDirection: "column",
    gap: 24,
  };

  const titleStyle: CSSProperties = {
    fontFamily: tokens.ffSerif,
    fontSize: 24,
    fontWeight: 600,
    color: tokens.ink,
    margin: 0,
  };

  const table: CSSProperties = {
    width: "100%",
    borderCollapse: "collapse",
    marginTop: 12,
  };

  const th: CSSProperties = {
    textAlign: "left",
    padding: "10px 12px",
    borderBottom: `1px solid ${tokens.rule}`,
    color: tokens.inkSoft,
    fontSize: 12,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
  };

  const td: CSSProperties = {
    padding: "12px",
    borderBottom: `1px solid ${tokens.ruleSoft || "rgba(0,0,0,0.05)"}`,
    fontSize: 13,
  };

  const badge: CSSProperties = {
    display: "inline-block",
    padding: "2px 6px",
    borderRadius: 4,
    fontSize: 10,
    fontFamily: tokens.ffMono,
    background: "rgba(214, 200, 173, 0.3)",
    color: tokens.accent,
  };

  const expandBtn: CSSProperties = {
    alignSelf: "flex-start",
    background: "transparent",
    border: `1px solid ${tokens.rule}`,
    padding: "8px 16px",
    borderRadius: 4,
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 500,
    color: tokens.inkSoft,
    display: "flex",
    alignItems: "center",
    gap: 8,
  };

  const panel: CSSProperties = {
    padding: 16,
    background: tokens.bgPaperCard,
    border: `1px solid ${tokens.rule}`,
    borderRadius: 6,
    fontSize: 13,
    color: tokens.inkSoft,
    lineHeight: 1.6,
  };

  if (loading) return <div style={{ color: tokens.inkSoft }}>{t("app:loading") || "Loading..."}</div>;
  if (error) return <div style={{ color: tokens.accent }}>Error loading footprint stats.</div>;
  if (!data) return null;

  const agents = Object.entries(data.by_agent);

  return (
    <div style={container} data-testid="footprint-tab">
      <h3 style={titleStyle}>🌱 Empreinte environnementale</h3>

      {agents.length === 0 ? (
        <div style={{ color: tokens.inkSoft, fontStyle: "italic" }}>
          Aucune donnée d'empreinte disponible pour le moment.
        </div>
      ) : (
        <table style={table}>
          <thead>
            <tr>
              <th style={th}>Agent</th>
              <th style={th}>Requêtes</th>
              <th style={th}>Consommation CO₂e</th>
              <th style={th}>Consommation Eau</th>
              <th style={th}>Type</th>
            </tr>
          </thead>
          <tbody>
            {agents.map(([name, bucket]) => (
              <tr key={name}>
                <td style={{ ...td, fontWeight: 500 }}>{name}</td>
                <td style={td}>{bucket.calls}</td>
                <td style={td}>
                  {bucket.has_estimate ? "~" : ""}
                  {bucket.gco2e.toFixed(1)} gCO₂e
                </td>
                <td style={td}>{Math.round(bucket.water_ml)} mL</td>
                <td style={td}>
                  {bucket.has_estimate ? (
                    <span data-testid="estimate-badge" style={badge}>
                      Estimation
                    </span>
                  ) : (
                    <span style={{ ...badge, background: "rgba(107, 79, 138, 0.1)" }}>
                      Mesure Réelle
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
        <span>Méthode d'estimation</span>
        <span>{methodOpen ? "▲" : "▼"}</span>
      </button>

      {methodOpen && (
        <div style={panel} data-testid="methode-panel">
          <p style={{ margin: 0 }}>
            L'estimation de l'impact environnemental est calculée à l'aide de la méthodologie{" "}
            <strong>EcoLogits</strong>, conforme à la norme d'Analyse du Cycle de Vie (ACV){" "}
            <strong>ISO 14044</strong>. Elle prend en compte les phases d'usage (GPU, PUE des centres de données){" "}
            ainsi que l'impact incorporé de la fabrication du matériel informatique.
          </p>
          <p style={{ margin: "12px 0 0 0", fontSize: 12, fontFamily: tokens.ffMono }}>
            Zone d'intensité carbone de la grille électrique configurée : <strong>{zone}</strong>
          </p>
        </div>
      )}
    </div>
  );
};

export default FootprintTab;
