import { type CSSProperties, type FC, useMemo, useState } from "react";
import { tokens } from "../_shared/armance-tokens";
import { displayAgentName } from "@/lib/agentNames";
import type { FootprintEquiv } from "@/lib/footprint";

export interface AgentStat {
  agent: string;
  tokens_in: number;
  tokens_out: number;
  cost: number;
  messages: number;
  gco2e?: number;
  water_ml?: number;
  has_estimate?: boolean;
  /** EcoLogits carbon confidence bounds (optional; render a range). */
  gco2e_min?: number | undefined;
  gco2e_max?: number | undefined;
  water_ml_min?: number | undefined;
  water_ml_max?: number | undefined;
}

const EN_DASH = "–";

/** `~[min – max] gCO₂e` when the bounds differ, else a flat `~mid gCO₂e`. */
function formatCo2(
  mid: number,
  min: number | undefined,
  max: number | undefined,
  estimate: boolean,
): string {
  const tilde = estimate ? "~" : "";
  if (min != null && max != null && Math.abs(max - min) > 1e-9) {
    return `${tilde}[${min.toFixed(1)} ${EN_DASH} ${max.toFixed(1)}] gCO₂e`;
  }
  return `${tilde}${mid.toFixed(1)} gCO₂e`;
}

export interface StatsDashboardProps {
  agents: AgentStat[];
  currency?: string;
  /** ADEME human-scale equivalences for the project total (optional). */
  equiv?: FootprintEquiv | undefined;
  /** Dominant carbon-intensity zone for the session (e.g. "WOR", "FRA"). */
  dominantZone?: string | null | undefined;
  /** Distinct providers used this session, for the method context note. */
  providers?: string[] | undefined;
  t: (key: string) => string;
}

const fmt = (n: number) => n.toLocaleString("fr-FR");

export const StatsDashboard: FC<StatsDashboardProps> = ({
  agents,
  currency = "€",
  equiv,
  dominantZone,
  providers,
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
          // Bounds fall back to the midpoint when a record carries no range.
          gco2e_min: acc.gco2e_min + (a.gco2e_min ?? a.gco2e ?? 0),
          gco2e_max: acc.gco2e_max + (a.gco2e_max ?? a.gco2e ?? 0),
          has_estimate: acc.has_estimate || Boolean(a.has_estimate),
        }),
        {
          tokens_in: 0, tokens_out: 0, cost: 0, messages: 0,
          gco2e: 0, water_ml: 0, gco2e_min: 0, gco2e_max: 0, has_estimate: false,
        },
      ),
    [agents],
  );

  const top5 = useMemo(
    () => [...agents].sort((a, b) => b.cost - a.cost).slice(0, 5),
    [agents],
  );

  // Footprint estimation methodology, folded in from the former Empreinte tab.
  const [methodOpen, setMethodOpen] = useState(false);

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
          label={`🌱 ${t("admin:stats.carbon_total")}`}
          value={
            totals.gco2e > 0
              ? formatCo2(totals.gco2e, totals.gco2e_min, totals.gco2e_max, totals.has_estimate)
              : t("visual:empty.deliberation.title")
          }
          accent
          accentColor="var(--accent-deep, #4a3666)"
        />
        <Card
          label={`💧 ${t("admin:stats.water_total")}`}
          value={totals.water_ml > 0 ? `~${Math.round(totals.water_ml)} mL` : t("visual:empty.deliberation.title")}
          accent
          accentColor="#2e6f40"
        />
      </div>

      {/* ADEME human-scale equivalences — make the abstract gCO₂e tangible. */}
      {equiv && totals.gco2e > 0 && (
        <div
          data-testid="footprint-equiv"
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 24,
            fontSize: 13,
            color: tokens.inkSoft,
            fontFamily: tokens.ffSans,
          }}
        >
          <Equiv label={t("admin:stats.equiv.phone_charges")} value={equiv.phone_charges} />
          <Equiv label={t("admin:stats.equiv.car_km")} value={equiv.car_km} />
          <Equiv label={t("admin:stats.equiv.water_glasses")} value={equiv.water_glasses} />
        </div>
      )}

      {/* Monetary & Token Statistics */}
      <div style={cards}>
        <Card label={t("admin:stats.tokens_in")} value={totals.tokens_in > 0 ? fmt(totals.tokens_in) : t("visual:empty.deliberation.title")} />
        <Card label={t("admin:stats.tokens_out")} value={totals.tokens_out > 0 ? fmt(totals.tokens_out) : t("visual:empty.deliberation.title")} />
        <Card
          label={t("admin:stats.cost")}
          value={totals.cost > 0 ? `${totals.cost.toFixed(3)} ${currency}` : t("visual:empty.deliberation.title")}
          accent
        />
        <Card label={t("admin:stats.messages")} value={totals.messages > 0 ? fmt(totals.messages) : t("visual:empty.deliberation.title")} />
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
                    {a.gco2e && a.gco2e > 0
                      ? formatCo2(a.gco2e, a.gco2e_min, a.gco2e_max, Boolean(a.has_estimate))
                      : "—"}
                  </span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <span style={{ fontSize: 11, color: tokens.inkSoft, textTransform: "uppercase", fontFamily: tokens.ffMono }}>
                    💧 {t("admin:stats.water")}
                  </span>
                  <span style={{ fontSize: 15, fontWeight: 600, color: tokens.ink }}>
                    {a.water_ml && a.water_ml > 0 ? `${Math.round(a.water_ml)} mL` : "—"}
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
                  {a.tokens_in > 0 || a.tokens_out > 0 ? (
                    <span>↑{fmt(a.tokens_in)} · ↓{fmt(a.tokens_out)}</span>
                  ) : (
                    <span>—</span>
                  )}
                </div>
                <div>
                  <span style={{ fontFamily: tokens.ffMono }}>{t("admin:stats.cost")}: </span>
                  {a.cost > 0 ? (
                    <span style={{ fontWeight: 600, color: tokens.accent }}>
                      {a.cost.toFixed(4)} {currency}
                    </span>
                  ) : (
                    <span>—</span>
                  )}
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

      <div>
        <button
          type="button"
          onClick={() => setMethodOpen((v) => !v)}
          aria-expanded={methodOpen}
          style={{
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
            fontFamily: tokens.ffSans,
          }}
        >
          <span aria-hidden="true">{methodOpen ? "▾" : "▸"}</span>
          <span>{t("admin:footprint.method")}</span>
        </button>
        {methodOpen && (
          <div
            data-testid="methode-panel"
            style={{
              marginTop: 12,
              padding: 16,
              background: tokens.bgPaperCard,
              border: `1px solid ${tokens.rule}`,
              borderRadius: 6,
              fontSize: 13,
              color: tokens.inkSoft,
              lineHeight: 1.6,
              display: "flex",
              flexDirection: "column",
              gap: 12,
            }}
          >
            <p style={{ margin: 0 }}>{t("admin:footprint.method_body")}</p>
            <p style={{ margin: 0 }}>{t("admin:footprint.method_tiers")}</p>
            {dominantZone && (
              <p style={{ margin: 0, fontFamily: tokens.ffMono, fontSize: 12 }}>
                {t("admin:footprint.method_zone_label")}: <strong>{dominantZone}</strong>
              </p>
            )}
            {providers && providers.length > 0 && (
              <div style={{ borderTop: `1px solid ${tokens.ruleSoft || tokens.rule}`, paddingTop: 10 }}>
                <div style={{ fontFamily: tokens.ffMono, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 6 }}>
                  {t("admin:footprint.method_providers_title")}
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
                  {providers.map((p) => (
                    <span
                      key={p}
                      style={{
                        fontFamily: tokens.ffMono, fontSize: 11,
                        padding: "2px 8px", borderRadius: 999,
                        border: `1px solid ${tokens.rule}`, color: tokens.ink,
                      }}
                    >
                      {p}
                    </span>
                  ))}
                </div>
                <p style={{ margin: 0 }}>{t("admin:footprint.method_provider_note")}</p>
              </div>
            )}
          </div>
        )}
      </div>
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

/** One "≈ N · label" human-scale equivalence chip. */
const Equiv: FC<{ label: string; value: number }> = ({ label, value }) => {
  const n = value >= 1 ? Math.round(value) : value.toFixed(1);
  return (
    <span style={{ display: "inline-flex", alignItems: "baseline", gap: 6 }}>
      <span style={{ fontWeight: 600, color: tokens.ink, fontFamily: tokens.ffMono }}>≈ {n}</span>
      <span>{label}</span>
    </span>
  );
};

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
