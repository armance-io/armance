import { type CSSProperties, type FC, useRef, useState } from "react";

/* ─── Types ──────────────────────────────────────────────────────────────── */

export type AgentPortraitSize = "sm" | "md" | "lg";

export interface AgentPortraitProps {
  /** Display name — drives the monogram initial and the img alt text. */
  name: string;
  /** Path to a PNG portrait. When absent a monogram is rendered. */
  src?: string;
  /** CSS colour for the monogram circle background (ignored when src is set). */
  tint: string;
  /** Controls the frame diameter. @default "md" */
  size?: AgentPortraitSize;
  /** Extra classes merged onto the root element. */
  className?: string;
}

/* ─── Constants ──────────────────────────────────────────────────────────── */

const SIZE_PX: Record<AgentPortraitSize, number> = {
  sm:  56,
  md:  88,
  lg: 128,
};

/* ─── Component ──────────────────────────────────────────────────────────── */

/**
 * `<AgentPortrait />` — oval portrait frame styled like a pinned photograph,
 * mirroring `.portrait-frame` from armance.io.
 *
 * Renders a `<img>` when `src` is supplied; falls back to a coloured
 * monogram (the first letter of `name` on a `tint` circle).
 *
 * Purely presentational — no i18n surface.
 */
export const AgentPortrait: FC<AgentPortraitProps> = ({
  name,
  src,
  tint,
  size = "md",
  className,
}) => {
  const px      = SIZE_PX[size];
  const initial = name.trim().charAt(0).toUpperCase();

  const [hovered, setHovered] = useState(false);

  /* Respect prefers-reduced-motion — read once at mount. */
  const prefersReduced = useRef<boolean>(
    typeof window !== "undefined"
      ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
      : false,
  );

  /* ── Styles ── */

  const frameStyle: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    width:  `${px}px`,
    height: `${px}px`,
    borderRadius: "999px",
    border: "2px solid var(--rule, #d6c8ad)",
    overflow: "hidden",
    flexShrink: 0,
    position: "relative",
    transform: hovered && !prefersReduced.current
      ? "rotate(2deg) translateY(-3px)"
      : "rotate(0deg)",
    boxShadow: hovered
      ? [
          "inset 0 2px 8px -4px rgba(42,37,32,0.10)",
          "0 12px 28px -8px rgba(42,37,32,0.22)",
          "0 2px 8px -3px rgba(42,37,32,0.12)",
        ].join(", ")
      : [
          "inset 0 2px 8px -4px rgba(42,37,32,0.20)",
          "0 4px 12px -6px rgba(42,37,32,0.10)",
        ].join(", "),
    transition: prefersReduced.current
      ? "none"
      : "transform 0.30s ease, box-shadow 0.30s ease",
  };

  const imgStyle: CSSProperties = {
    width: "100%",
    height: "100%",
    objectFit: "cover",
    objectPosition: "center top",
    display: "block",
    /* matches armance.io .portrait-frame img */
    filter: "contrast(1.02) saturate(0.95)",
  };

  const monogramStyle: CSSProperties = {
    width: "100%",
    height: "100%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: tint,
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontStyle: "normal",
    /* 0.6 × frame diameter */
    fontSize: `${Math.round(px * 0.6)}px`,
    lineHeight: 1,
    /* cream text legible on the saturated character tints */
    color: "oklch(0.97 0.012 82)",

  };

  const rootClassName = [
    "agent-portrait",
    `agent-portrait--${size}`,
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className={rootClassName}
      style={frameStyle}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      /* a11y: expose as image with the agent's name */
      role={src ? undefined : "img"}
      aria-label={!src ? name : undefined}
    >
      {src ? (
        <img src={src} alt={name} style={imgStyle} />
      ) : (
        <span style={monogramStyle} aria-hidden="true">
          {initial}
        </span>
      )}
    </div>
  );
};

export default AgentPortrait;
