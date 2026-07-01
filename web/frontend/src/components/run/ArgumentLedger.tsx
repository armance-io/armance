import { type CSSProperties, type FC } from "react";

/* ─── Types ──────────────────────────────────────────────────────────────── */

type ArgStatus = "retained" | "rejected" | "open";

interface Argument {
  id: string;
  claim: string;
  status: ArgStatus;
  proposed_by: string[];
  proposed_in_steps: string[];
  rejected_by?: string;
  rejection_reason?: string;
  sources: string[];
  weight?: number;
}

interface SourceRef {
  kind: string;
  ref: string;
  label: string;
}

export interface ArgumentLedgerProps {
  arguments: Argument[];
  sourcesById: Record<string, SourceRef>;
  onClickSource: (sourceId: string) => void;
  t: (key: string) => string;
}

/* ─── Component ──────────────────────────────────────────────────────────── */

export const ArgumentLedger: FC<ArgumentLedgerProps> = ({
  arguments: args,
  sourcesById,
  onClickSource,
  t,
}) => {
  const retained = args.filter(
    (a) => a.status === "retained" || a.status === "open",
  );
  const rejected = args.filter((a) => a.status === "rejected");

  const rootStyle: CSSProperties = {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "16px",
    alignItems: "start",
  };

  const colTitleStyle: CSSProperties = {
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontSize: "18px",
    color: "var(--ink, #2a2520)",
    margin: "0 0 12px",
  };

  const colStyle: CSSProperties = {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  };

  return (
    <div>
      <style>{`
        @media (prefers-reduced-motion: reduce) {
          * { transition: none !important; }
        }
      `}</style>

      <div style={rootStyle}>
        <div style={colStyle}>
          <h4 style={colTitleStyle}>{t("run:ledger.retained")}</h4>
          {retained.map((a) => (
            <ArgumentCard
              key={a.id}
              arg={a}
              sourcesById={sourcesById}
              onClickSource={onClickSource}
              t={t}
              variant="retained"
            />
          ))}
        </div>
        <div style={colStyle}>
          <h4 style={colTitleStyle}>{t("run:ledger.rejected")}</h4>
          {rejected.map((a) => (
            <ArgumentCard
              key={a.id}
              arg={a}
              sourcesById={sourcesById}
              onClickSource={onClickSource}
              t={t}
              variant="rejected"
            />
          ))}
        </div>
      </div>
    </div>
  );
};

/* ─── Single Card ────────────────────────────────────────────────────────── */

const ArgumentCard: FC<{
  arg: Argument;
  sourcesById: Record<string, SourceRef>;
  onClickSource: (sourceId: string) => void;
  t: (key: string) => string;
  variant: "retained" | "rejected";
}> = ({ arg, sourcesById, onClickSource, t, variant }) => {
  const isRejected = variant === "rejected";

  const cardStyle: CSSProperties = {
    border: "1px solid var(--rule, #d6c8ad)",
    padding: "12px",
    display: "flex",
    flexDirection: "column",
    gap: "8px",
    opacity: isRejected ? 0.75 : 1,
    background: "var(--bg-paper-card, #faf6ef)",
  };

  const claimStyle: CSSProperties = {
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontStyle: "italic",
    fontSize: "15px",
    lineHeight: 1.45,
    color: "var(--ink, #2a2520)",
    margin: 0,
    textDecoration: isRejected ? "line-through" : "none",
  };

  const metaStyle: CSSProperties = {
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "12px",
    color: "var(--ink-soft, #5b5145)",
    lineHeight: 1.45,
  };

  const reasonStyle: CSSProperties = {
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontStyle: "italic",
    fontSize: "12px",
    color: "var(--ink-soft, #5b5145)",
    lineHeight: 1.45,
  };

  const chipRowStyle: CSSProperties = {
    display: "flex",
    flexWrap: "wrap",
    gap: "4px",
  };

  const chipStyle: CSSProperties = {
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "10px",
    letterSpacing: "0.04em",
    padding: "2px 8px",
    borderRadius: "999px",
    border: "1px solid var(--rule, #d6c8ad)",
    background: "var(--bg-paper-deep, #e8dfcd)",
    color: "var(--accent, #6b4f8a)",
    cursor: "pointer",
    transition: "border-color 120ms ease",
  };

  const weightStyle: CSSProperties = {
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "10px",
    padding: "2px 8px",
    borderRadius: "999px",
    border: "1px solid var(--accent-soft, #b7a4c9)",
    color: "var(--accent, #6b4f8a)",
  };

  return (
    <div style={cardStyle}>
      <p style={claimStyle}>{arg.claim}</p>

      <div style={metaStyle}>
        {t("run:ledger.proposed_by")}: {arg.proposed_by.join(", ")}
      </div>

      {isRejected && arg.rejected_by && (
        <div style={metaStyle}>
          {t("run:ledger.rejected_by")}: {arg.rejected_by}
        </div>
      )}

      {isRejected && arg.rejection_reason && (
        <div style={reasonStyle}>{arg.rejection_reason}</div>
      )}

      {arg.weight !== undefined && !isRejected && (
        <span style={weightStyle} title={t("run:ledger.weight_tooltip")}>
          {t("run:ledger.weight")}: {arg.weight}
        </span>
      )}

      {arg.sources.length > 0 && (
        <div style={chipRowStyle}>
          {arg.sources.map((sid) => {
            const src = sourcesById[sid];
            return (
              <button
                key={sid}
                style={chipStyle}
                title={t("run:ledger.source_tooltip")}
                onClick={() => onClickSource(sid)}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor =
                    "var(--accent, #6b4f8a)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor =
                    "var(--rule, #d6c8ad)";
                }}
              >
                📖 {src?.label ?? sid}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default ArgumentLedger;
