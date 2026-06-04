import { type CSSProperties, type FC } from "react";

/* ─── Types ──────────────────────────────────────────────────────────────── */

export interface ModeBadgeProps {
  mode: "interactive" | "autonomous";
  t: (key: string) => string;
}

/* ─── Component ──────────────────────────────────────────────────────────── */

export const ModeBadge: FC<ModeBadgeProps> = ({ mode, t }) => {
  const isInteractive = mode === "interactive";

  const label = t(`run:mode.${mode}_label`);
  const hint = t(`run:mode.${mode}_hint`);

  /* ─── Styles ───────────────────────────────────────────────────────────── */

  const badgeStyle: CSSProperties = {
    height: "24px",
    border: "1px solid var(--rule, #d6c8ad)",
    padding: "0 10px",
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "9px",
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    borderRadius: "2px",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    cursor: "help",
    userSelect: "none",
    whiteSpace: "nowrap",
    outline: "none",

    /* State-dependent styling */
    color: isInteractive
      ? "var(--accent-deep, #4a3666)"
      : "var(--accent, #6b4f8a)",
    background: isInteractive
      ? "var(--bg-paper, #f4ede0)"
      : "color-mix(in srgb, var(--accent-soft, #b7a4c9) 20%, transparent)",
  };

  return (
    <span
      className="mode-badge"
      style={badgeStyle}
      title={hint}
      role="status"
      aria-label={`${t("run:mode.title_aria")}: ${label}. ${hint}`}
      tabIndex={0}
    >
      <style>{`
        .mode-badge:hover,
        .mode-badge:focus {
          border-color: var(--accent, #6b4f8a) !important;
        }
        @media (prefers-reduced-motion: reduce) {
          .mode-badge {
            transition: none !important;
          }
        }
      `}</style>
      {label}
    </span>
  );
};

export default ModeBadge;
