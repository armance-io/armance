import { type CSSProperties, type FC } from "react";
import { Handle, Position } from "@xyflow/react";

/* ─── Types ──────────────────────────────────────────────────────────────── */

type StepStatus =
  | "queued"
  | "working"
  | "completed"
  | "failed"
  | "cancelled"
  | "skipped";

export interface StepNodeData extends Record<string, unknown> {
  step_id: string;
  role: string;
  status: StepStatus;
  /** Who actually spoke (manifest `agent`, failover-aware). */
  agent?: string;
  duration_ms?: number;
}

export interface StepNodeProps {
  data: StepNodeData;
  selected?: boolean | undefined;
}

/* ─── Helpers ────────────────────────────────────────────────────────────── */

function fmtDuration(ms?: number): string {
  if (ms === undefined) return "";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

const STATUS_DOT_COLOR: Record<StepStatus, string> = {
  queued: "var(--ink-faint, #9c8e7e)",
  working: "hsl(35, 30%, 60%)",
  completed: "hsl(120, 15%, 55%)",
  failed: "hsl(0, 30%, 65%)",
  cancelled: "var(--ink-faint, #9c8e7e)",
  skipped: "var(--ink-faint, #9c8e7e)",
};

// Soft, muted backgrounds per DESIGN.md gems — done steps tint sage,
// working steps warm ochre, failed terracotta. Others keep the parchment.
const STATUS_BG: Record<StepStatus, string> = {
  queued: "var(--bg-paper, #f4ede0)",
  working: "color-mix(in srgb, hsl(35, 30%, 60%) 12%, var(--bg-paper, #f4ede0))",
  completed: "color-mix(in srgb, hsl(120, 15%, 55%) 14%, var(--bg-paper, #f4ede0))",
  failed: "color-mix(in srgb, hsl(0, 30%, 65%) 12%, var(--bg-paper, #f4ede0))",
  cancelled: "var(--bg-paper, #f4ede0)",
  skipped: "var(--bg-paper, #f4ede0)",
};

/* ─── Component ──────────────────────────────────────────────────────────── */

export const StepNode: FC<StepNodeProps> = ({ data, selected = false }) => {
  const { step_id, role, status, agent, duration_ms } = data;

  const isCancelled = status === "cancelled";
  const isSkipped = status === "skipped";
  const isWorking = status === "working";

  const isCompleted = status === "completed";
  const borderColor = selected
    ? "var(--accent, #6b4f8a)"
    : isWorking
      ? "var(--accent, #6b4f8a)"
      : isCompleted
        ? "hsl(120, 15%, 55%)"
        : "var(--rule, #d6c8ad)";

  const boxStyle: CSSProperties = {
    width: "200px",
    height: "72px",
    border: `1px solid ${borderColor}`,
    borderRadius: "2px",
    background: STATUS_BG[status],
    padding: "8px 12px",
    display: "flex",
    flexDirection: "column",
    justifyContent: "space-between",
    boxSizing: "border-box",
    opacity: isSkipped ? 0.6 : 1,
    textDecoration: isCancelled ? "line-through" : "none",
    color: isCancelled
      ? "var(--ink-soft, #5b5145)"
      : "var(--ink, #2a2520)",
    position: "relative",
    transition: "border-color 160ms ease, background 240ms ease",
    boxShadow: isWorking
      ? "0 0 0 3px color-mix(in srgb, var(--accent, #6b4f8a) 14%, transparent)"
      : "none",
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
    animation: isWorking ? "stepnode-pulse 1.2s ease-in-out infinite" : "none",
  };

  const durationStyle: CSSProperties = {
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "10px",
    color: "var(--ink-faint, #9c8e7e)",
  };

  /* Real (but invisible) React Flow handles — edges cannot anchor to a
     custom node without <Handle> components; plain divs draw no edges. */
  const handleStyle: CSSProperties = {
    width: 1,
    height: 1,
    minWidth: 1,
    minHeight: 1,
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
        @keyframes stepnode-spin { to { transform: rotate(360deg); } }
        @media (prefers-reduced-motion: reduce) {
          * { animation: none !important; transition: none !important; }
        }
      `}</style>

      <div style={idStyle}>{step_id}</div>
      <div style={roleStyle}>{agent ? `${agent} · ${role}` : role}</div>
      <div style={bottomRowStyle}>
        {isWorking ? (
          <span
            aria-hidden="true"
            style={{
              width: "12px", height: "12px", borderRadius: "999px",
              border: "2px solid color-mix(in srgb, var(--accent,#6b4f8a) 25%, transparent)",
              borderTopColor: "var(--accent, #6b4f8a)",
              display: "inline-block",
              animation: "stepnode-spin 0.8s linear infinite",
            }}
          />
        ) : isCompleted ? (
          <svg width="12" height="12" viewBox="0 0 14 14" fill="none"
            stroke="hsl(120, 15%, 45%)" strokeWidth="2.2" strokeLinecap="round"
            strokeLinejoin="round" aria-hidden="true" style={{ display: "block" }}>
            <path d="M2.5 7.5l3 3 6-7" />
          </svg>
        ) : (
          <span style={dotStyle} aria-hidden="true" />
        )}
        {duration_ms !== undefined && (
          <span style={durationStyle}>{fmtDuration(duration_ms)}</span>
        )}
      </div>

      <Handle
        type="target"
        position={Position.Left}
        isConnectable={false}
        style={handleStyle}
      />
      <Handle
        type="source"
        position={Position.Right}
        isConnectable={false}
        style={handleStyle}
      />
    </div>
  );
};

export default StepNode;
