import { type CSSProperties, type FC, useState } from "react";

import { Fleuron } from "../Fleuron";

/* ─── Types ──────────────────────────────────────────────────────────────── */

export interface EmptyShellProps {
  /** Editorial title — rendered in italic Instrument Serif. */
  title: string;
  /** Two-line hint — rendered in Inter `var(--ink-soft)`. */
  hint: string;
  /** Optional CTA button label. Renders the button only when `onCta` is also provided. */
  ctaLabel?: string | undefined;
  /** CTA click handler. Renders the button only when `ctaLabel` is also provided. */
  onCta?: (() => void) | undefined;
}

/* ─── Component ──────────────────────────────────────────────────────────── */

/**
 * `<EmptyShell />` — internal layout primitive used by the three EmptyState
 * variants (EmptyLibrary, EmptyWorkflow, EmptySession). Composes:
 *   ❦ (Fleuron size="sm") → italic title → ink-soft hint → optional CTA.
 *
 * Not meant to be consumed directly outside `components/visual/EmptyState/`.
 */
export const EmptyShell: FC<EmptyShellProps> = ({
  title,
  hint,
  ctaLabel,
  onCta,
}) => {
  const [hovered, setHovered] = useState(false);

  const showCta = ctaLabel !== undefined && onCta !== undefined;

  const wrapStyle: CSSProperties = {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    textAlign: "center",
    padding: "56px 24px",
    maxWidth: "460px",
    margin: "0 auto",
  };

  const titleStyle: CSSProperties = {
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontStyle: "italic",
    fontWeight: 400,
    fontSize: "30px",
    lineHeight: 1.15,
    letterSpacing: "-0.01em",
    color: "var(--ink, #2a2520)",
    margin: "4px 0 12px",
    textWrap: "balance" as CSSProperties["textWrap"],
  };

  const hintStyle: CSSProperties = {
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "15px",
    lineHeight: 1.55,
    color: "var(--ink-soft, #5b5145)",
    margin: 0,
    maxWidth: "34ch",
    textWrap: "balance" as CSSProperties["textWrap"],
  };

  const ctaStyle: CSSProperties = {
    marginTop: "24px",
    padding: "10px 22px",
    borderRadius: "999px",
    border: `1px solid ${hovered ? "var(--accent, #6b4f8a)" : "var(--rule, #d6c8ad)"}`,
    background: hovered ? "var(--accent, #6b4f8a)" : "transparent",
    color: hovered ? "var(--bg-paper, #f4ede0)" : "var(--ink, #2a2520)",
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "14px",
    fontWeight: 500,
    letterSpacing: "0.01em",
    cursor: "pointer",
    transition:
      "background 0.20s ease, color 0.20s ease, border-color 0.20s ease",
  };

  return (
    <div role="status" aria-live="polite" style={wrapStyle}>
      <Fleuron size="sm" />
      <h2 style={titleStyle}>{title}</h2>
      <p style={hintStyle}>{hint}</p>
      {showCta && (
        <button
          type="button"
          onClick={onCta}
          style={ctaStyle}
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
        >
          {ctaLabel}
        </button>
      )}
    </div>
  );
};

export default EmptyShell;
