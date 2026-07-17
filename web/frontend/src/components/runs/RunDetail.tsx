import {
  type CSSProperties,
  type FC,
  useState,
  useCallback,
} from "react";
import type { RunDerivation, RunQuality } from "@/lib/api";
import {
  RunStepRow,
  STATUS_GEMS,
  fmtDuration,
  fmtTokens,
  type RunStep,
} from "@/components/runs/RunStepRow";
import {
  RunQualityPanel,
  RunDerivationNote,
} from "@/components/runs/RunQualityPanel";

/* ─── Types ──────────────────────────────────────────────────────────────── */

export interface Run {
  run_id: string;
  workflow: string;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  status: string;
  tokens_in: number | null;
  tokens_out: number | null;
  cost_usd: number | null;
  steps: RunStep[];
  quality?: RunQuality;
  derived_from?: RunDerivation[];
}

export interface RunDetailProps {
  run: Run;
  onStepExpand?: (stepId: string) => Promise<void>;
  onOpenRun?: (runId: string) => void;
  t: (key: string) => string;
}

function fmtCost(c: number | null, t: (k: string) => string): string {
  if (c === null) return t("runs:detail.cost_na");
  return `$${c.toFixed(4)}`;
}

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
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

/* ─── Main Component ─────────────────────────────────────────────────────── */

export const RunDetail: FC<RunDetailProps> = ({
  run,
  onStepExpand,
  onOpenRun,
  t,
}) => {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggleStep = useCallback(async (id: string) => {
    const isExpanding = !expanded.has(id);
    if (isExpanding && onStepExpand) {
      await onStepExpand(id);
    }
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, [expanded, onStepExpand]);

  const rootStyle: CSSProperties = {
    display: "flex",
    flexDirection: "column",
    height: "100%",
    minHeight: 0,
    background: "var(--bg-paper, #f4ede0)",
    color: "var(--ink, #2a2520)",
  };

  const metaMono: CSSProperties = {
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "11px",
    letterSpacing: "0.04em",
    color: "var(--ink-soft, #5b5145)",
  };

  const totalTokens =
    run.tokens_in !== null && run.tokens_out !== null
      ? run.tokens_in + run.tokens_out
      : null;

  return (
    <div style={rootStyle} data-testid="run-detail">
      <style>{`
        @keyframes rundetail-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
        @media (prefers-reduced-motion: reduce) {
          * { animation: none !important; transition: none !important; }
        }
      `}</style>

      <div
        style={{
          position: "sticky",
          top: 0,
          zIndex: 10,
          background: "var(--bg-paper-card, #faf6ef)",
          borderBottom: "1px solid var(--rule, #d6c8ad)",
          padding: "16px 24px",
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
          gap: "8px",
        }}
      >
        <h2
          style={{
            fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
            fontSize: "22px",
            lineHeight: 1.2,
            color: "var(--ink, #2a2520)",
            margin: 0,
          }}
        >
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
        <div style={{ display: "flex", flexWrap: "wrap", gap: "16px", ...metaMono }}>
          <span
            style={{
              color: "var(--ink, #2a2520)",
              fontWeight: 500,
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <span
              style={{
                display: "inline-block",
                width: "10px",
                height: "10px",
                borderRadius: "50%",
                backgroundColor: STATUS_GEMS[run.status]?.bg || "var(--ink-faint)",
                border: `1px solid ${STATUS_GEMS[run.status]?.border || "transparent"}`,
                flexShrink: 0,
                animation: STATUS_GEMS[run.status]?.pulse
                  ? "rundetail-pulse 1s infinite alternate"
                  : "none",
              }}
              aria-hidden="true"
            />
            {t(`runs:detail.status.${run.status}`)}
          </span>
          <span>
            {t("runs:detail.duration")}: {fmtDuration(run.duration_ms)}
          </span>
          <span>
            {t("runs:detail.tokens")}: {fmtTokens(totalTokens)}
          </span>
          <span>
            {t("runs:detail.cost")}: {fmtCost(run.cost_usd, t)}
          </span>
        </div>
        {run.derived_from && run.derived_from.length > 0 && (
          <RunDerivationNote
            derivedFrom={run.derived_from}
            onOpenRun={onOpenRun}
            t={t}
          />
        )}
      </div>

      <div style={{ flex: 1, minHeight: 0, overflow: "auto" }}>
        {run.quality && <RunQualityPanel quality={run.quality} t={t} />}

        {run.steps.map((step) => (
          <RunStepRow
            key={step.id}
            step={step}
            expanded={expanded.has(step.id)}
            onToggle={() => toggleStep(step.id)}
            t={t}
          />
        ))}

        <div
          data-testid="run-totals-footer"
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: "20px",
            padding: "14px 16px",
            ...metaMono,
            borderTop: "1px solid var(--rule, #d6c8ad)",
            background: "var(--bg-paper-card, #faf6ef)",
          }}
        >
          <span>
            {t("runs:detail.total_tokens")}: {fmtTokens(totalTokens)}
          </span>
          <span>
            {t("runs:detail.total_cost")}: {fmtCost(run.cost_usd, t)}
          </span>
        </div>
      </div>
    </div>
  );
};

export default RunDetail;
