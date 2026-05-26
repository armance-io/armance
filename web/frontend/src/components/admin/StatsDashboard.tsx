import { type CSSProperties, type FC, useMemo } from "react";
import { tokens } from "../_shared/armance-tokens";

export interface AgentStat {
  agent: string;
  tokens_in: number;
  tokens_out: number;
  cost: number;
  messages: number;
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
        }),
        { tokens_in: 0, tokens_out: 0, cost: 0, messages: 0 },
      ),
    [agents],
  );

  const top5 = useMemo(
    () => [...agents].sort((a, b) => b.cost - a.cost).slice(0, 5),
    [agents],
  );

  const maxBar = useMemo(
    () => Math.max(1, ...agents.flatMap((a) => [a.tokens_in, a.tokens_out])),
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

  return (
    <div style={root}>
      <div style={cards}>
        <Card label={t("admin:stats.tokens_in")} value={fmt(totals.tokens_in)} />
        <Card label={t("admin:stats.tokens_out")} value={fmt(totals.tokens_out)} />
        <Card
          label={t("admin:stats.cost")}
          value={`${totals.cost.toFixed(2)} ${currency}`}
          accent
        />
        <Card label={t("admin:stats.messages")} value={fmt(totals.messages)} />
      </div>

      <Section title={t("admin:stats.per_agent")}>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {agents.map((a) => (
            <div key={a.agent}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: 13,
                  marginBottom: 6,
                }}
              >
                <span style={{ fontFamily: tokens.ffSerif, fontSize: 16 }}>{a.agent}</span>
                <span style={{ color: tokens.inkSoft, fontFamily: tokens.ffMono, fontSize: 12 }}>
                  ↑{fmt(a.tokens_in)} · ↓{fmt(a.tokens_out)}
                </span>
              </div>
              <div style={{ display: "flex", gap: 4 }}>
                <Bar value={a.tokens_in} max={maxBar} color={tokens.accent} />
                <Bar value={a.tokens_out} max={maxBar} color={tokens.accentSoft} />
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
              <span>{a.agent}</span>
              <span style={{ fontFamily: tokens.ffMono, fontSize: 13, color: tokens.ink }}>
                {a.cost.toFixed(2)} {currency}
              </span>
            </li>
          ))}
        </ol>
      </Section>
    </div>
  );
};

const Card: FC<{ label: string; value: string; accent?: boolean }> = ({
  label,
  value,
  accent,
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
        color: accent ? tokens.accent : tokens.ink,
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

const Bar: FC<{ value: number; max: number; color: string }> = ({ value, max, color }) => (
  <div
    style={{
      flex: 1,
      height: 10,
      background: tokens.bgPaperDeep,
      border: `1px solid ${tokens.rule}`,
      overflow: "hidden",
    }}
  >
    <div
      style={{
        width: `${(value / max) * 100}%`,
        height: "100%",
        background: color,
        transition: "width 240ms ease",
      }}
    />
  </div>
);

export default StatsDashboard;
