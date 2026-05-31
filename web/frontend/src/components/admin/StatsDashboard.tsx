import { type CSSProperties, type FC, useMemo } from "react";
import { tokens } from "../_shared/armance-tokens";
import { displayAgentName } from "@/lib/agentNames";

export interface AgentStat {
  agent: string;
  tokens_in: number;
  tokens_out: number;
  cost: number;
  messages: number;
  gco2e?: number;
  water_ml?: number;
  has_estimate?: boolean;
}

export interface StatsDashboardProps {
  agents: AgentStat[];
  currency?: string;
  t: (key: string) => string;
}

const fmt = (n: number) => n.toLocaleString("fr-FR");

export const StatsDashboard: FC<StatsDashboardProps> = ({
  agents,
  currency = "€",
  t,
}) => {
  const totals = useMemo(
    () =>
      agents.reduce(
        (acc, a) => ({
          tokens_in: acc.tokens_in + a.tokens_in,
          tokens_out: acc.tokens_out + a.tokens_out,
          cost: acc.cost + a.cost,
          messages: acc.messages + a.messages,
          gco2e: acc.gco2e + (a.gco2e ?? 0),
          water_ml: acc.water_ml + (a.water_ml ?? 0),
        }),
        { tokens_in: 0, tokens_out: 0, cost: 0, messages: 0, gco2e: 0, water_ml: 0 },
      ),
    [agents],
  );

  const top5 = useMemo(
    () => [...agents].sort((a, b) => b.cost - a.cost).slice(0, 5),
    [agents],
  );

  const root: CSSProperties = {
    fontFamily: tokens.ffSans,
    color: tokens.ink,
    display: "flex",
    flexDirection: "column",
    gap: 32,
  };
  const cards: CSSProperties = {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: 16,
  };

  if (agents.length === 0) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: tokens.inkSoft, fontFamily: tokens.ffSans }}>
        <p style={{ fontSize: 16, marginBottom: 12, fontWeight: 500 }}>{t("visual:empty.deliberation.title")}</p>
        <p style={{ fontSize: 13 }}>{t("visual:empty.deliberation.hint")}</p>
      </div>
    );
  }

  return (
    <div style={root}>
      {/* Environmental Footprint Cards (Top Priority) */}
      <div style={{ ...cards, gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
        <Card
          label="🌱 Empreinte Carbone Totale"
          value={`~${totals.gco2e.toFixed(1)} gCO₂e`}
          accent
          accentColor="var(--accent-deep, #4a3666)"
        />
        <Card
          label="💧 Consommation d'Eau Totale"
          value={`~${Math.round(totals.water_ml)} mL`}
          accent
          accentColor="#2e6f40"
        />
      </div>

      {/* Monetary & Token Statistics */}
      <div style={cards}>
        <Card label={t("admin:stats.tokens_in")} value={fmt(totals.tokens_in)} />
        <Card label={t("admin:stats.tokens_out")} value={fmt(totals.tokens_out)} />
        <Card
          label={t("admin:stats.cost")}
          value={`${totals.cost.toFixed(3)} ${currency}`}
          accent
        />
        <Card label={t("admin:stats.messages")} value={fmt(totals.messages)} />
      </div>

      {/* Per Agent section with Environmental Footprint listed ABOVE monetary cost */}
      <Section title={t("admin:stats.per_agent")}>
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {agents.map((a) => (
            <div
              key={a.agent}
              style={{
                background: tokens.bgPaperCard,
                border: `1px solid ${tokens.rule}`,
                padding: "16px 20px",
                borderRadius: 4,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: 14,
                  fontWeight: 600,
                  marginBottom: 12,
                  borderBottom: `1px solid ${tokens.ruleSoft || "rgba(0,0,0,0.05)"}`,
                  paddingBottom: 6,
                }}
              >
                <span style={{ fontFamily: tokens.ffSerif, fontSize: 18 }}>{displayAgentName(a.agent)}</span>
                <span style={{ color: tokens.inkSoft, fontFamily: tokens.ffMono, fontSize: 12 }}>
                  {a.messages} {t("admin:stats.messages")}
                </span>
              </div>

              {/* Environmental metrics listed FIRST */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 16,
                  marginBottom: 12,
                }}
              >
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <span style={{ fontSize: 11, color: tokens.inkSoft, textTransform: "uppercase", fontFamily: tokens.ffMono }}>
                    🌱 {t("admin:stats.carbon")}
                  </span>
                  <span style={{ fontSize: 15, fontWeight: 600, color: tokens.ink }}>
                    {a.has_estimate ? "~" : ""}{a.gco2e?.toFixed(1) ?? "0.0"} gCO₂e
                  </span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <span style={{ fontSize: 11, color: tokens.inkSoft, textTransform: "uppercase", fontFamily: tokens.ffMono }}>
                    💧 {t("admin:stats.water")}
                  </span>
                  <span style={{ fontSize: 15, fontWeight: 600, color: tokens.ink }}>
                    {Math.round(a.water_ml ?? 0)} mL
                  </span>
                </div>
              </div>

              {/* Tokens & Cost listed SECOND */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 16,
                  fontSize: 12,
                  color: tokens.inkSoft,
                  borderTop: `1px solid ${tokens.ruleSoft || "rgba(0,0,0,0.03)"}`,
                  paddingTop: 8,
                }}
              >
                <div>
                  <span style={{ fontFamily: tokens.ffMono }}>Tokens: </span>
                  <span>↑{fmt(a.tokens_in)} · ↓{fmt(a.tokens_out)}</span>
                </div>
                <div>
                  <span style={{ fontFamily: tokens.ffMono }}>{t("admin:stats.cost")}: </span>
                  <span style={{ fontWeight: 600, color: tokens.accent }}>
                    {a.cost.toFixed(4)} {currency}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Section>

      <Section title={t("admin:stats.top5_cost")}>
        <ol style={{ margin: 0, padding: 0, listStyle: "none" }}>
          {top5.map((a, i) => (
            <li
              key={a.agent}
              style={{
                display: "grid",
                gridTemplateColumns: "32px 1fr auto",
                gap: 12,
                padding: "10px 14px",
                borderBottom: `1px solid ${tokens.rule}`,
                alignItems: "center",
              }}
            >
              <span style={{ fontFamily: tokens.ffSerif, fontSize: 22, color: tokens.accent }}>
                {i + 1}
              </span>
              <span>{displayAgentName(a.agent)}</span>
              <span style={{ fontFamily: tokens.ffMono, fontSize: 13, color: tokens.ink }}>
                {a.cost.toFixed(4)} {currency}
              </span>
            </li>
          ))}
        </ol>
      </Section>
    </div>
  );
};

const Card: FC<{ label: string; value: string; accent?: boolean; accentColor?: string }> = ({
  label,
  value,
  accent,
  accentColor,
}) => (
  <div
    style={{
      background: tokens.bgPaperCard,
      border: `1px solid ${tokens.rule}`,
      padding: "20px 22px",
      display: "flex",
      flexDirection: "column",
      gap: 8,
    }}
  >
    <span
      style={{
        fontFamily: tokens.ffMono,
        fontSize: 11,
        textTransform: "uppercase",
        letterSpacing: "0.08em",
        color: tokens.inkSoft,
      }}
    >
      {label}
    </span>
    <span
      style={{
        fontFamily: tokens.ffSerif,
        fontSize: 32,
        letterSpacing: "-0.01em",
        color: accent ? (accentColor || tokens.accent) : tokens.ink,
      }}
    >
      {value}
    </span>
  </div>
);

const Section: FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <section>
    <h3
      style={{
        fontFamily: tokens.ffSerif,
        fontSize: 22,
        margin: "0 0 16px",
        fontStyle: "italic",
        color: tokens.ink,
      }}
    >
      {title}
    </h3>
    {children}
  </section>
);

export default StatsDashboard;
