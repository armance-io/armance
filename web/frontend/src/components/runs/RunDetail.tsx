import {
  type CSSProperties,
  type FC,
  useState,
  useCallback,
  useRef,
} from "react";
import { DeliverableReader } from "@/components/library/DeliverableReader";

/* ─── Types ──────────────────────────────────────────────────────────────── */

type RunStatus = "running" | "completed" | "failed" | "cancelled";

interface Step {
  id: string;
  role: string;
  status: RunStatus;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  tokens_in: number | null;
  tokens_out: number | null;
  output: string;
}

export interface Run {
  run_id: string;
  workflow: string;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  status: RunStatus;
  tokens_in: number | null;
  tokens_out: number | null;
  cost_usd: number | null;
  steps: Step[];
}

export interface RunDetailProps {
  run: Run;
  t: (key: string) => string;
}

/* ─── Helpers ────────────────────────────────────────────────────────────── */

const STATUS_EMOJI: Record<RunStatus, string> = {
  completed: "✅",
  failed: "❌",
  running: "⏳",
  cancelled: "⏭",
};

const STATUS_COLOUR: Record<RunStatus, string> = {
  completed: "var(--accent-deep, #4a3666)",
  failed: "oklch(0.55 0.18 25)",
  running: "oklch(0.65 0.15 85)",
  cancelled: "var(--ink-soft, #5b5145)",
};

function fmtDuration(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${ms}ms`;
  const s = (ms / 1000).toFixed(1);
  return `${s}s`;
}

function fmtTokens(n: number | null): string {
  if (n === null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function fmtCost(c: number | null, t: (k: string) => string): string {
  if (c === null) return t("runs:detail.cost_na");
  return `$${c.toFixed(4)}`;
}

function fmtDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

/* ─── Subcomponents ──────────────────────────────────────────────────────── */

const StepRow: FC<{
  step: Step;
  expanded: boolean;
  onToggle: () => void;
  t: (key: string) => string;
}> = ({ step, expanded, onToggle, t }) => {
  const rowStyle: CSSProperties = {
    borderBottom: "1px solid var(--rule, #d6c8ad)",
  };

  const headerStyle: CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    padding: "12px 16px",
    cursor: "pointer",
    background: "transparent",
    border: "none",
    width: "100%",
    textAlign: "left",
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "14px",
    color: "var(--ink, #2a2520)",
    transition: "background 120ms ease",
  };

  const idStyle: CSSProperties = {
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "12px",
    color: "var(--ink-soft, #5b5145)",
    flexShrink: 0,
    minWidth: "80px",
  };

  const roleStyle: CSSProperties = {
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontStyle: "italic",
    fontSize: "15px",
    color: "var(--accent, #6b4f8a)",
    flex: 1,
    minWidth: 0,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  };

  const metaStyle: CSSProperties = {
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "11px",
    color: "var(--ink-faint, #9c8e7e)",
    flexShrink: 0,
  };

  const emojiStyle: CSSProperties = {
    flexShrink: 0,
    fontSize: "14px",
    animation:
      step.status === "running"
        ? "rundetail-pulse 1.6s ease-in-out infinite"
        : "none",
  };

  const chevronStyle: CSSProperties = {
    flexShrink: 0,
    width: "14px",
    height: "14px",
    color: "var(--ink-faint, #9c8e7e)",
    transform: expanded ? "rotate(90deg)" : "rotate(0deg)",
    transition: "transform 180ms ease",
  };

  const bodyStyle: CSSProperties = {
    padding: expanded ? "0 16px 16px" : "0 16px",
    maxHeight: expanded ? "600px" : "0",
    overflow: "hidden",
    transition: "max-height 280ms ease, padding 280ms ease",
  };

  return (
    <div style={rowStyle}>
      <button
        style={headerStyle}
        onClick={onToggle}
        aria-expanded={expanded}
        aria-label={`${t("runs:detail.step")} ${step.id}`}
        onMouseEnter={(e) => {
          e.currentTarget.style.background =
            "var(--bg-paper-deep, #e8dfcd)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = "transparent";
        }}
      >
        <svg
          style={chevronStyle}
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M6 4l4 4-4 4" />
        </svg>
        <span style={emojiStyle} aria-hidden="true">
          {STATUS_EMOJI[step.status]}
        </span>
        <span style={idStyle}>{step.id}</span>
        <span style={roleStyle}>{step.role}</span>
        <span style={metaStyle}>{fmtDuration(step.duration_ms)}</span>
        <span style={metaStyle}>
          {fmtTokens(
            step.tokens_in !== null && step.tokens_out !== null
              ? step.tokens_in + step.tokens_out
              : null,
          )}
        </span>
      </button>
      <div style={bodyStyle}>
        {expanded && step.output && (
          <DeliverableReader
            title={`${step.role} — ${step.id}`}
            markdown={step.output}
            downloadUrl="#"
            downloadFormat="md"
            sourcePath={step.id}
            t={t}
          />
        )}
      </div>
    </div>
  );
};

/* ─── Main Component ─────────────────────────────────────────────────────── */

export const RunDetail: FC<RunDetailProps> = ({ run, t }) => {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const headerRef = useRef<HTMLDivElement>(null);

  const toggleStep = useCallback((id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const rootStyle: CSSProperties = {
    display: "flex",
    flexDirection: "column",
    height: "100%",
    minHeight: 0,
    background: "var(--bg-paper, #f4ede0)",
    color: "var(--ink, #2a2520)",
  };

  const stickyHeaderStyle: CSSProperties = {
    position: "sticky",
    top: 0,
    zIndex: 10,
    background: "var(--bg-paper-card, #faf6ef)",
    borderBottom: "1px solid var(--rule, #d6c8ad)",
    padding: "16px 24px",
    flexShrink: 0,
  };

  const titleStyle: CSSProperties = {
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontSize: "22px",
    lineHeight: 1.2,
    color: "var(--ink, #2a2520)",
    margin: "0 0 8px",
  };

  const metaRowStyle: CSSProperties = {
    display: "flex",
    flexWrap: "wrap",
    gap: "16px",
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "11px",
    letterSpacing: "0.04em",
    color: "var(--ink-soft, #5b5145)",
  };

  const statusStyle: CSSProperties = {
    color: STATUS_COLOUR[run.status],
    fontWeight: 500,
  };

  const listStyle: CSSProperties = {
    flex: 1,
    minHeight: 0,
    overflow: "auto",
  };

  return (
    <div style={rootStyle}>
      <style>{`
        @keyframes rundetail-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
        @media (prefers-reduced-motion: reduce) {
          * { animation: none !important; transition: none !important; }
        }
      `}</style>

      <div ref={headerRef} style={stickyHeaderStyle}>
        <h2 style={titleStyle}>
          {run.workflow}{" "}
          <span
            style={{
              fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
              fontSize: "14px",
              color: "var(--ink-faint, #9c8e7e)",
              fontWeight: 400,
            }}
          >
            {fmtDate(run.started_at)}
          </span>
        </h2>
        <div style={metaRowStyle}>
          <span style={statusStyle}>
            {STATUS_EMOJI[run.status]}{" "}
            {t(`runs:detail.status.${run.status}`)}
          </span>
          <span>
            {t("runs:detail.duration")}: {fmtDuration(run.duration_ms)}
          </span>
          <span>
            {t("runs:detail.tokens")}:{" "}
            {fmtTokens(
              run.tokens_in !== null && run.tokens_out !== null
                ? run.tokens_in + run.tokens_out
                : null,
            )}
          </span>
          <span>
            {t("runs:detail.cost")}: {fmtCost(run.cost_usd, t)}
          </span>
        </div>
      </div>

      <div style={listStyle}>
        {run.steps.map((step) => (
          <StepRow
            key={step.id}
            step={step}
            expanded={expanded.has(step.id)}
            onToggle={() => toggleStep(step.id)}
            t={t}
          />
        ))}
      </div>
    </div>
  );
};

export default RunDetail;
