import { type CSSProperties, type FC } from "react";
import { PulseDot } from "@/components/_shared/PulseDot";

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
    return <div style={rootStyle} aria-hidden="true" />;
  }

  return (
    <div style={rootStyle} role="status" aria-live="polite">
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
      <PulseDot color={busy.colour} />
      <span style={labelStyle}>
        {t("chat:bottom.thinking").replace("{name}", busy.name)}
      </span>
    </div>
  );
};

export default BottomSpinner;
