import { type CSSProperties, type FC } from "react";
import { MarkdownRenderer } from "@/components/render/MarkdownRenderer";
import type { RunDerivation, RunQuality } from "@/lib/api";

/* ─── Fleuron separator (❦, per DESIGN.md §5) ────────────────────────────── */

const Fleuron: FC = () => (
  <div
    aria-hidden="true"
    style={{
      display: "flex",
      alignItems: "center",
      gap: "12px",
      margin: "4px 0 12px",
    }}
  >
    <span
      style={{
        flex: 1,
        height: "1px",
        background:
          "linear-gradient(to left, var(--rule, #d6c8ad), transparent)",
      }}
    />
    <span
      style={{
        color: "var(--accent-soft, #b7a4c9)",
        fontSize: "16px",
        lineHeight: 1,
      }}
    >
      ❦
    </span>
    <span
      style={{
        flex: 1,
        height: "1px",
        background:
          "linear-gradient(to right, var(--rule, #d6c8ad), transparent)",
      }}
    />
  </div>
);

/* ─── Derivation note ────────────────────────────────────────────────────── */

export const RunDerivationNote: FC<{
  derivedFrom: RunDerivation[];
  onOpenRun?: ((runId: string) => void) | undefined;
  t: (key: string) => string;
}> = ({ derivedFrom, onOpenRun, t }) => {
  if (derivedFrom.length === 0) return null;
  return (
    <div
      data-testid="run-derivation-note"
      style={{
        fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
        fontStyle: "italic",
        fontSize: "14px",
        color: "var(--ink-soft, #5b5145)",
        display: "flex",
        flexWrap: "wrap",
        alignItems: "baseline",
        gap: "6px",
      }}
    >
      <span>{t("runs:detail.derived_from")}</span>
      {derivedFrom.map((d) => (
        <span key={d.run_id} style={{ display: "inline-flex", alignItems: "baseline", gap: "4px" }}>
          <button
            type="button"
            data-testid={`run-parent-link-${d.run_id}`}
            onClick={() => onOpenRun?.(d.run_id)}
            style={{
              fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
              fontSize: "12px",
              fontStyle: "normal",
              color: "var(--accent, #6b4f8a)",
              background: "transparent",
              border: "none",
              padding: 0,
              cursor: onOpenRun ? "pointer" : "default",
              textDecoration: "underline",
              textDecorationColor: "var(--accent-soft, #b7a4c9)",
              textUnderlineOffset: "3px",
            }}
          >
            {d.run_id}
          </button>
          {d.overrides.length > 0 && (
            <span
              style={{
                fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
                fontSize: "11px",
                fontStyle: "normal",
                color: "var(--ink-faint, #9c8e7e)",
              }}
              data-testid={`run-overrides-${d.run_id}`}
            >
              ({d.overrides.map((o) => o.step).join(", ")})
            </span>
          )}
        </span>
      ))}
    </div>
  );
};

/* ─── Quality panel ──────────────────────────────────────────────────────── */

export interface RunQualityPanelProps {
  quality: RunQuality;
  t: (key: string) => string;
}

/**
 * The Creuset quality report — a square archive card, opened by a fleuron,
 * rendering the report markdown. Renders nothing when no report exists.
 */
export const RunQualityPanel: FC<RunQualityPanelProps> = ({ quality, t }) => {
  if (!quality.present || !quality.markdown) return null;

  const cardStyle: CSSProperties = {
    background: "var(--bg-paper-card, #faf6ef)",
    border: "1px solid var(--rule, #d6c8ad)",
    borderRadius: "2px",
    padding: "16px 20px 20px",
    margin: "16px",
  };

  return (
    <section
      style={cardStyle}
      data-testid="run-quality-panel"
      aria-label={t("runs:detail.quality_title")}
    >
      <h3
        style={{
          fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
          fontStyle: "italic",
          fontSize: "18px",
          fontWeight: 400,
          color: "var(--ink, #2a2520)",
          margin: "0 0 4px",
          textAlign: "center",
        }}
      >
        {t("runs:detail.quality_title")}
      </h3>
      <Fleuron />
      <MarkdownRenderer markdown={quality.markdown} t={t} />
    </section>
  );
};

export default RunQualityPanel;
