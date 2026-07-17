import { type CSSProperties, type FC } from "react";
import { DeliverableReader } from "@/components/library/DeliverableReader";
import {
  type CrucibleStage,
  stageGem,
  stepCostLabel,
} from "@/components/workflow/stepNodeStage";

/* ─── Types ──────────────────────────────────────────────────────────────── */

export interface RunStep {
  id: string;
  role: string;
  status: string;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  tokens_in: number | null;
  tokens_out: number | null;
  cost_usd?: number | null;
  stage?: CrucibleStage | null;
  family?: string | null;
  agent?: string | null;
  provided?: boolean;
  error?: string | null;
  output: string;
}

/** Soft Belle-Époque status gems shared by the run header and step rows. */
export const STATUS_GEMS: Record<
  string,
  { bg: string; border: string; pulse?: boolean }
> = {
  queued: { bg: "var(--ink-faint, #9c8e7e)", border: "rgba(42, 37, 32, 0.2)" },
  working: { bg: "hsl(35, 30%, 60%)", border: "hsl(35, 30%, 50%)", pulse: true },
  running: { bg: "hsl(35, 30%, 60%)", border: "hsl(35, 30%, 50%)", pulse: true },
  completed: { bg: "hsl(120, 15%, 55%)", border: "hsl(120, 15%, 45%)" },
  failed: { bg: "hsl(0, 30%, 65%)", border: "hsl(0, 30%, 55%)" },
  cancelled: { bg: "var(--ink-faint, #9c8e7e)", border: "rgba(42, 37, 32, 0.2)" },
  skipped: { bg: "var(--ink-faint, #9c8e7e)", border: "rgba(42, 37, 32, 0.2)" },
  provided: { bg: "var(--accent-soft, #b7a4c9)", border: "var(--accent, #6b4f8a)" },
};

export function fmtDuration(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function fmtTokens(n: number | null): string {
  if (n === null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

/* ─── Component ──────────────────────────────────────────────────────────── */

const MONO: CSSProperties = {
  fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
  fontSize: "11px",
  color: "var(--ink-faint, #9c8e7e)",
  flexShrink: 0,
};

export const RunStepRow: FC<{
  step: RunStep;
  expanded: boolean;
  onToggle: () => void;
  t: (key: string) => string;
}> = ({ step, expanded, onToggle, t }) => {
  const gem = stageGem(step.stage);
  const cost = stepCostLabel(step.cost_usd, step.tokens_in, step.tokens_out);

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

  return (
    <div
      style={{ borderBottom: "1px solid var(--rule, #d6c8ad)" }}
      data-testid={`run-step-row-${step.id}`}
    >
      <button
        style={headerStyle}
        onClick={onToggle}
        aria-expanded={expanded}
        aria-label={`${t("runs:detail.step")} ${step.id}`}
        data-testid={`run-step-toggle-${step.id}`}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = "var(--bg-paper-deep, #e8dfcd)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = "transparent";
        }}
      >
        <svg
          style={{
            flexShrink: 0,
            width: "14px",
            height: "14px",
            color: "var(--ink-faint, #9c8e7e)",
            transform: expanded ? "rotate(90deg)" : "rotate(0deg)",
            transition: "transform 180ms ease",
          }}
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
        <span
          style={{
            display: "inline-block",
            width: "10px",
            height: "10px",
            borderRadius: "50%",
            backgroundColor: STATUS_GEMS[step.status]?.bg || "var(--ink-faint)",
            border: `1px solid ${STATUS_GEMS[step.status]?.border || "transparent"}`,
            flexShrink: 0,
            animation: STATUS_GEMS[step.status]?.pulse
              ? "rundetail-pulse 1s infinite alternate"
              : "none",
          }}
          title={t(`runs:detail.status.${step.status}`)}
          aria-hidden="true"
        />
        <span
          style={{
            ...MONO,
            fontSize: "12px",
            color: "var(--ink-soft, #5b5145)",
            minWidth: "80px",
          }}
        >
          {step.id}
        </span>
        {gem && (
          <span
            style={badgeStyle}
            data-testid={`run-step-stage-${step.id}`}
            data-stage={step.stage}
          >
            {t(`workflow:stage.${gem.key}`)}
          </span>
        )}
        <span
          style={{
            fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
            fontStyle: "italic",
            fontSize: "15px",
            color: "var(--accent, #6b4f8a)",
            flex: 1,
            minWidth: 0,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {step.agent ? `${step.agent} · ${step.role}` : step.role}
        </span>
        {step.provided && (
          <span
            style={{
              fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
              fontStyle: "italic",
              fontSize: "12px",
              color: "var(--accent, #6b4f8a)",
              flexShrink: 0,
            }}
            title={t("workflow:step.provided_hint")}
            data-testid={`run-step-provided-${step.id}`}
          >
            {t("workflow:step.provided")}
          </span>
        )}
        {step.family && (
          <span style={MONO} data-testid={`run-step-family-${step.id}`}>
            {step.family}
          </span>
        )}
        <span style={MONO}>{fmtDuration(step.duration_ms)}</span>
        {cost && (
          <span style={MONO} data-testid={`run-step-cost-${step.id}`}>
            {cost}
          </span>
        )}
      </button>
      <div
        style={{
          padding: expanded ? "0 16px 16px" : "0 16px",
          maxHeight: expanded ? "600px" : "0",
          overflow: "hidden",
          transition: "max-height 280ms ease, padding 280ms ease",
        }}
      >
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

export default RunStepRow;
