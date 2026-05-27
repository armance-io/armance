import { type CSSProperties, type FC } from "react";

/* ─── Types ──────────────────────────────────────────────────────────────── */

interface PanelMember {
  name: string;
  role: string;
  persona: string;
  axis: string;
  provider: string;
  model: string;
  reasoning?: "low" | "medium" | "high";
  portraitSrc?: string;
  colour: string;
}

export interface PanelCardsProps {
  panel: PanelMember[];
  onApprove: () => void;
  onAskAlternative: () => void;
  t: (key: string) => string;
}

/* ─── Component ──────────────────────────────────────────────────────────── */

export const PanelCards: FC<PanelCardsProps> = ({
  panel,
  onApprove,
  onAskAlternative,
  t,
}) => {
  const rootStyle: CSSProperties = {
    display: "flex",
    flexDirection: "column",
    gap: "20px",
  };

  const rowStyle: CSSProperties = {
    display: "flex",
    flexWrap: "wrap",
    gap: "16px",
  };

  const actionsStyle: CSSProperties = {
    display: "flex",
    gap: "12px",
    justifyContent: "center",
    paddingTop: "8px",
  };

  const primaryBtnStyle: CSSProperties = {
    padding: "12px 24px",
    borderRadius: "999px",
    border: "none",
    background: "var(--accent, #6b4f8a)",
    color: "var(--bg-paper, #f4ede0)",
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "14px",
    fontWeight: 500,
    cursor: "pointer",
    transition: "background 160ms ease",
  };

  const ghostBtnStyle: CSSProperties = {
    padding: "12px 24px",
    borderRadius: "999px",
    border: "1px solid var(--rule, #d6c8ad)",
    background: "transparent",
    color: "var(--ink, #2a2520)",
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "14px",
    fontWeight: 500,
    cursor: "pointer",
    transition: "border-color 160ms ease, background 160ms ease",
  };

  return (
    <div style={rootStyle}>
      <style>{`
        .panel-card {
          width: 240px;
          min-height: 280px;
          border: 1px solid var(--rule, #d6c8ad);
          padding: 16px;
          display: flex;
          flex-direction: column;
          gap: 12px;
          background: var(--bg-paper-card, #faf6ef);
          transition: transform 200ms ease, box-shadow 200ms ease;
        }
        .panel-card:hover {
          transform: translateY(-3px);
          box-shadow: var(--shadow-lift,
            0 8px 32px -10px rgba(42,37,32,0.16),
            0 2px 8px -3px rgba(42,37,32,0.08));
        }
        @media (prefers-reduced-motion: reduce) {
          .panel-card { transition: none !important; }
        }
      `}</style>

      <div style={rowStyle}>
        {panel.map((member) => (
          <PanelCard key={member.name} member={member} t={t} />
        ))}
      </div>

      <div style={actionsStyle}>
        <button
          style={primaryBtnStyle}
          onClick={onApprove}
          onMouseEnter={(e) => {
            e.currentTarget.style.background =
              "var(--accent-deep, #4a3666)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background =
              "var(--accent, #6b4f8a)";
          }}
        >
          {t("panel:approve")}
        </button>
        <button
          style={ghostBtnStyle}
          onClick={onAskAlternative}
          onMouseEnter={(e) => {
            e.currentTarget.style.background =
              "var(--bg-paper-deep, #e8dfcd)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
          }}
        >
          {t("panel:ask_alternative")}
        </button>
      </div>
    </div>
  );
};

/* ─── Single Card ────────────────────────────────────────────────────────── */

const PanelCard: FC<{ member: PanelMember; t: (key: string) => string }> = ({
  member,
  t: _t,
}) => {
  const portraitStyle: CSSProperties = {
    width: "48px",
    height: "48px",
    borderRadius: "999px",
    overflow: "hidden",
    flexShrink: 0,
    border: "1px solid var(--rule, #d6c8ad)",
    background: member.colour,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontSize: "24px",
    color: "oklch(0.97 0.012 82)",
  };

  const nameStyle: CSSProperties = {
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontSize: "20px",
    color: "var(--ink, #2a2520)",
  };

  const roleChipStyle: CSSProperties = {
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "10px",
    letterSpacing: "0.12em",
    textTransform: "uppercase",
    color: "var(--ink-soft, #5b5145)",
  };

  const axisChipStyle: CSSProperties = {
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontStyle: "italic",
    fontSize: "13px",
    padding: "3px 10px",
    borderRadius: "999px",
    background: "var(--accent-soft, #b7a4c9)",
    color: "var(--bg-paper, #f4ede0)",
  };

  const voiceStyle: CSSProperties = {
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "13px",
    lineHeight: 1.5,
    color: "var(--ink-soft, #5b5145)",
    flex: 1,
  };

  const modelStyle: CSSProperties = {
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "10px",
    color: "var(--ink-faint, #9c8e7e)",
    letterSpacing: "0.04em",
  };

  return (
    <div className="panel-card">
      <div style={portraitStyle} aria-hidden="true">
        {member.portraitSrc ? (
          <img
            src={member.portraitSrc}
            alt=""
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
            }}
          />
        ) : (
          member.name.charAt(0).toUpperCase()
        )}
      </div>
      <div style={nameStyle}>{member.name}</div>
      <div style={roleChipStyle}>{member.role}</div>
      <span style={axisChipStyle}>{member.axis}</span>
      <div style={voiceStyle}>{member.persona}</div>
      <div style={modelStyle}>
        {member.provider} · {member.model}
      </div>
    </div>
  );
};

export default PanelCards;
