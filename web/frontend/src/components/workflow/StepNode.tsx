import { type CSSProperties, type FC } from "react";
import { Handle, Position } from "@xyflow/react";
import {
  type CrucibleStage,
  stageGem,
  fmtDuration,
  stepCostLabel,
} from "@/components/workflow/stepNodeStage";
import {
  STATUS_BG,
  STATUS_DOT_COLOR,
  type StepStatus,
} from "@/components/workflow/stepNodeStatus";

/* ─── Types ──────────────────────────────────────────────────────────────── */

export interface StepNodeData extends Record<string, unknown> {
  step_id: string;
  role: string;
  status: StepStatus;
  /** Who actually spoke (manifest `agent`, failover-aware). */
  agent?: string;
  duration_ms?: number;
  /** Creuset stage — draft/critique/synthesis/gate/standard. */
  stage?: CrucibleStage | null;
  /** Model family that answered (runtime, from the manifest). */
  family?: string | null;
  cost_usd?: number | null;
  tokens_in?: number | null;
  tokens_out?: number | null;
  /** Human-provided step (override / re-run injection). */
  provided?: boolean;
  /** Injected translator so the badge label is i18n'd. */
  t?: (key: string) => string;
}

export interface StepNodeProps {
  data: StepNodeData;
  selected?: boolean | undefined;
}


/* ─── Component ──────────────────────────────────────────────────────────── */

export const StepNode: FC<StepNodeProps> = ({ data, selected = false }) => {
  const {
    step_id,
    role,
    status,
    agent,
    duration_ms,
    stage,
    family,
    cost_usd,
    tokens_in,
    tokens_out,
    provided,
    t,
  } = data;

  const isCancelled = status === "cancelled";
  const isSkipped = status === "skipped";
  const isWorking = status === "working";
  const isCompleted = status === "completed";

  const gem = stageGem(stage);
  const cost = stepCostLabel(cost_usd, tokens_in, tokens_out);
  const tr = t ?? ((k: string) => k);

  const borderColor = selected
    ? "var(--accent, #6b4f8a)"
    : isWorking
      ? "var(--accent, #6b4f8a)"
      : isCompleted
        ? "hsl(120, 15%, 55%)"
        : "var(--rule, #d6c8ad)";

  const boxStyle: CSSProperties = {
    width: "200px",
    minHeight: "72px",
    border: `1px solid ${borderColor}`,
    borderRadius: "2px",
    background: STATUS_BG[status],
    padding: "8px 12px",
    display: "flex",
    flexDirection: "column",
    gap: "3px",
    boxSizing: "border-box",
    opacity: isSkipped ? 0.6 : 1,
    textDecoration: isCancelled ? "line-through" : "none",
    color: isCancelled ? "var(--ink-soft, #5b5145)" : "var(--ink, #2a2520)",
    position: "relative",
    transition: "border-color 160ms ease, background 240ms ease",
    boxShadow: isWorking
      ? "0 0 0 3px color-mix(in srgb, var(--accent, #6b4f8a) 14%, transparent)"
      : "none",
  };

  const topRowStyle: CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    justifyContent: "space-between",
  };

  const idStyle: CSSProperties = {
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "10px",
    color: "var(--ink-soft, #5b5145)",
    letterSpacing: "0.04em",
    lineHeight: 1.2,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  };

  const badgeStyle: CSSProperties = gem
    ? {
        fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
        fontSize: "9px",
        fontWeight: 600,
        letterSpacing: "0.06em",
        textTransform: "uppercase",
        padding: "1px 6px",
        borderRadius: "2px",
        color: gem.hue,
        background: `color-mix(in srgb, ${gem.hue} 14%, var(--bg-paper-card, #faf6ef))`,
        border: `1px solid color-mix(in srgb, ${gem.hue} 40%, transparent)`,
        flexShrink: 0,
        lineHeight: 1.4,
      }
    : {};

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

  const mono: CSSProperties = {
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "10px",
    color: "var(--ink-faint, #9c8e7e)",
  };

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
    <div
      style={boxStyle}
      aria-label={`${step_id} — ${role} — ${status}`}
      data-testid={`step-node-${step_id}`}
    >
      <style>{`
        @keyframes stepnode-pulse { 0%,100%{opacity:1;} 50%{opacity:0.35;} }
        @keyframes stepnode-spin { to { transform: rotate(360deg); } }
        @media (prefers-reduced-motion: reduce) {
          * { animation: none !important; transition: none !important; }
        }
      `}</style>

      <div style={topRowStyle}>
        <span style={idStyle}>{step_id}</span>
        {gem && (
          <span
            style={badgeStyle}
            data-testid={`stage-badge-${step_id}`}
            data-stage={stage}
          >
            {tr(`workflow:stage.${gem.key}`)}
          </span>
        )}
      </div>

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
          <span
            style={{
              width: "6px", height: "6px", borderRadius: "999px",
              background: STATUS_DOT_COLOR[status], flexShrink: 0,
            }}
            aria-hidden="true"
          />
        )}
        {duration_ms !== undefined && duration_ms !== null && (
          <span style={mono}>{fmtDuration(duration_ms)}</span>
        )}
        {cost && (
          <span style={mono} data-testid={`step-cost-${step_id}`}>{cost}</span>
        )}
        {family && (
          <span
            style={{ ...mono, marginLeft: "auto", opacity: 0.9 }}
            data-testid={`step-family-${step_id}`}
            title={family}
          >
            {family}
          </span>
        )}
        {provided && (
          <span
            style={{
              marginLeft: family ? "0" : "auto",
              color: "var(--accent, #6b4f8a)",
              fontStyle: "italic",
              fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
              fontSize: "11px",
            }}
            data-testid={`step-provided-${step_id}`}
            title={tr("workflow:step.provided_hint")}
          >
            {tr("workflow:step.provided")}
          </span>
        )}
      </div>

      <Handle type="target" position={Position.Left} isConnectable={false} style={handleStyle} />
      <Handle type="source" position={Position.Right} isConnectable={false} style={handleStyle} />
    </div>
  );
};

export default StepNode;
