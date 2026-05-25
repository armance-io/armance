import { type CSSProperties, type FC } from "react";

/* ─── Types ──────────────────────────────────────────────────────────────── */

export interface BottomSpinnerProps {
  busy: null | {
    name: string;
    portraitSrc?: string;
    colour: string;
  };
  t: (key: string) => string;
}

/* ─── Component ──────────────────────────────────────────────────────────── */

export const BottomSpinner: FC<BottomSpinnerProps> = ({ busy, t }) => {
  const isActive = busy !== null;

  const rootStyle: CSSProperties = {
    height: isActive ? "32px" : "0",
    overflow: "hidden",
    background: isActive
      ? "var(--bg-paper-deep, #e8dfcd)"
      : "transparent",
    borderTop: isActive
      ? "1px solid var(--rule, #d6c8ad)"
      : "none",
    display: "flex",
    alignItems: "center",
    gap: "8px",
    padding: isActive ? "0 16px" : "0",
    transition:
      "height 200ms ease, padding 200ms ease, background 200ms ease, border-top 200ms ease",
  };

  const portraitStyle: CSSProperties = {
    width: "20px",
    height: "20px",
    borderRadius: "999px",
    overflow: "hidden",
    flexShrink: 0,
    border: "1px solid var(--rule, #d6c8ad)",
    background: busy?.colour ?? "transparent",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontSize: "11px",
    color: "oklch(0.97 0.012 82)",
  };

  const dotStyle: CSSProperties = {
    width: "6px",
    height: "6px",
    borderRadius: "999px",
    background: busy?.colour ?? "var(--accent, #6b4f8a)",
    flexShrink: 0,
    animation: "bottomspin-pulse 1.4s ease-in-out infinite",
  };

  const labelStyle: CSSProperties = {
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontStyle: "italic",
    fontSize: "12px",
    color: "var(--ink-soft, #5b5145)",
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  };

  if (!isActive) {
    return (
      <div style={rootStyle} aria-hidden="true">
        <style>{`
          @keyframes bottomspin-pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
          }
          @media (prefers-reduced-motion: reduce) {
            * { animation: none !important; transition: none !important; }
          }
        `}</style>
      </div>
    );
  }

  return (
    <div style={rootStyle} role="status" aria-live="polite">
      <style>{`
        @keyframes bottomspin-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
        @media (prefers-reduced-motion: reduce) {
          * { animation: none !important; transition: none !important; }
        }
      `}</style>

      <div style={portraitStyle} aria-hidden="true">
        {busy.portraitSrc ? (
          <img
            src={busy.portraitSrc}
            alt=""
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
            }}
          />
        ) : (
          busy.name.charAt(0).toUpperCase()
        )}
      </div>
      <span style={dotStyle} aria-hidden="true" />
      <span style={labelStyle}>
        {t("chat:bottom.thinking").replace("{name}", busy.name)}
      </span>
    </div>
  );
};

export default BottomSpinner;
