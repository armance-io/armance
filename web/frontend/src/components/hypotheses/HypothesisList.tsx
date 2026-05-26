import { type CSSProperties, type FC } from "react";

/* ─── Types ──────────────────────────────────────────────────────────────── */

interface Hypothesis {
  step_id: string;
  text: string;
  invalidator?: string;
}

export interface HypothesisListProps {
  hypotheses: Hypothesis[];
  t: (key: string) => string;
}

/* ─── Component ──────────────────────────────────────────────────────────── */

export const HypothesisList: FC<HypothesisListProps> = ({
  hypotheses,
  t,
}) => {
  const rootStyle: CSSProperties = {
    display: "flex",
    flexDirection: "column",
    gap: "0",
  };

  const headerStyle: CSSProperties = {
    textAlign: "center",
    marginBottom: "24px",
  };

  const titleStyle: CSSProperties = {
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontSize: "22px",
    color: "var(--ink, #2a2520)",
    margin: "0 0 8px",
  };

  const fleuronStyle: CSSProperties = {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "14px",
    padding: "8px 0",
  };

  const fleuronRuleStyle: CSSProperties = {
    width: "56px",
    height: "0",
    borderTop: "1px solid var(--rule, #d6c8ad)",
  };

  const fleuronGlyphStyle: CSSProperties = {
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontSize: "16px",
    color: "var(--accent, #6b4f8a)",
    lineHeight: 1,
  };

  const itemStyle: CSSProperties = {
    borderLeft: "2px solid var(--accent, #6b4f8a)",
    padding: "12px 16px",
    marginBottom: "12px",
  };

  const markerStyle: CSSProperties = {
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "10px",
    letterSpacing: "0.12em",
    textTransform: "uppercase",
    color: "var(--accent-deep, #4a3666)",
    marginBottom: "6px",
    fontWeight: 500,
  };

  const textStyle: CSSProperties = {
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontStyle: "italic",
    fontSize: "16px",
    lineHeight: 1.5,
    color: "var(--ink, #2a2520)",
    margin: "0 0 6px",
  };

  const invalidatorStyle: CSSProperties = {
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontStyle: "italic",
    fontSize: "13px",
    lineHeight: 1.45,
    color: "var(--ink-soft, #5b5145)",
    margin: "0 0 4px",
  };

  const stepStyle: CSSProperties = {
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "10px",
    color: "var(--ink-faint, #9c8e7e)",
    letterSpacing: "0.06em",
  };

  return (
    <div style={rootStyle}>
      <div style={headerStyle}>
        <h3 style={titleStyle}>{t("hypotheses:title")}</h3>
        <div style={fleuronStyle} aria-hidden="true">
          <span style={fleuronRuleStyle} />
          <span style={fleuronGlyphStyle}>❦</span>
          <span style={fleuronRuleStyle} />
        </div>
      </div>

      {hypotheses.map((h, i) => (
        <div key={h.step_id + i} style={itemStyle}>
          <div style={markerStyle}>{t("hypotheses:marker")}</div>
          <p style={textStyle}>{h.text}</p>
          {h.invalidator && (
            <p style={invalidatorStyle}>
              {t("hypotheses:invalidator")}: {h.invalidator}
            </p>
          )}
          <div style={stepStyle}>{h.step_id}</div>
        </div>
      ))}
    </div>
  );
};

export default HypothesisList;
