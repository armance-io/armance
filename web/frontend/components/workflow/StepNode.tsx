import { type CSSProperties, type FC } from "react";

/* ─── Types ──────────────────────────────────────────────────────────────── */

type StepStatus =
  | "queued"
  | "working"
  | "completed"
  | "failed"
  | "cancelled"
  | "skipped";

export interface StepNodeData {
  step_id: string;
  role: string;
  status: StepStatus;
  duration_ms?: number;
  streaming?: boolean;
}

export interface StepNodeProps {
  data: StepNodeData;
  selected?: boolean;
}

/* ─── Helpers ────────────────────────────────────────────────────────────── */

function fmtDuration(ms?: number): string {
  if (ms === undefined) return "";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

const STATUS_DOT_COLOR: Record<StepStatus, string> = {
  queued: "var(--ink-soft, #5b5145)",
  working: "var(--accent, #6b4f8a)",
  completed: "var(--accent-deep, #4a3666)",
  failed: "oklch(0.55 0.18 25)",
  cancelled: "var(--ink-soft, #5b5145)",
  skipped: "var(--ink-faint, #9c8e7e)",
};

/* ─── Component ──────────────────────────────────────────────────────────── */

export const StepNode: FC<StepNodeProps> = ({ data, selected = false }) => {
  const { step_id, role, status, duration_ms, streaming } = data;

  const isCancelled = status === "cancelled";
  const isSkipped = status === "skipped";
  const isWorking = status === "working";

  const boxStyle: CSSProperties = {
    width: "200px",
    height: "72px",
    border: `1px solid ${selected ? "var(--accent, #6b4f8a)" : "var(--rule, #d6c8ad)"}`,
    borderRadius: "2px",
    background: "var(--bg-paper, #f4ede0)",
    padding: "10px",
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    gap: "4px",
    opacity: isSkipped ? 0.6 : 1,
    textDecoration: isCancelled ? "line-through" : "none",
    color: isCancelled
      ? "var(--ink-soft, #5b5145)"
      : "var(--ink, #2a2520)",
    position: "relative",
    transition: "border-color 160ms ease",
  };

  const idStyle: CSSProperties = {
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "10px",
    color: "var(--ink-soft, #5b5145)",
    letterSpacing: "0.04em",
    lineHeight: 1.2,
  };

  const roleStyle: CSSProperties = {
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontStyle: "italic",
    fontSize: "14px",
    color: "var(--accent, #6b4f8a)",
    lineHeight: 1.2,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  };

  const bottomRowStyle: CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: "6px",
  };

  const dotStyle: CSSProperties = {
    width: "6px",
    height: "6px",
    borderRadius: "999px",
    background: STATUS_DOT_COLOR[status],
    flexShrink: 0,
    animation: isWorking
      ? streaming
        ? "stepnode-pulse 400ms ease-in-out infinite alternate"
        : "stepnode-pulse 1.2s ease-in-out infinite"
      : "none",
  };

  const durationStyle: CSSProperties = {
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "10px",
    color: "var(--ink-faint, #9c8e7e)",
  };

  /* Hidden handles for React Flow */
  const handleStyle: CSSProperties = {
    position: "absolute",
    width: "1px",
    height: "1px",
    background: "transparent",
    border: "none",
    opacity: 0,
  };

  return (
    <div style={boxStyle} aria-label={`${step_id} — ${role} — ${status}`}>
      <style>{`
        @keyframes stepnode-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.35; }
        }
        @media (prefers-reduced-motion: reduce) {
          * { animation: none !important; transition: none !important; }
        }
      `}</style>

      <div style={idStyle}>{step_id}</div>
      <div style={roleStyle}>{role}</div>
      <div style={bottomRowStyle}>
        <span style={dotStyle} aria-hidden="true" />
        {duration_ms !== undefined && (
          <span style={durationStyle}>{fmtDuration(duration_ms)}</span>
        )}
      </div>

      {/* Left handle (target) */}
      <div
        style={{ ...handleStyle, left: 0, top: "50%" }}
        data-handleid="left"
        data-handlepos="left"
      />
      {/* Right handle (source) */}
      <div
        style={{ ...handleStyle, right: 0, top: "50%" }}
        data-handleid="right"
        data-handlepos="right"
      />
    </div>
  );
};

export default StepNode;
