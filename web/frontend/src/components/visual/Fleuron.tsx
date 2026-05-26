import type { CSSProperties, FC } from "react";

export type FleuronSize = "sm" | "md" | "lg";

export interface FleuronProps {
  /**
   * Controls the glyph size, flanking-rule length and vertical padding.
   * @default "md"
   */
  size?: FleuronSize;
  /**
   * Extra classes appended to the root element.
   */
  className?: string;
}

interface FleuronMetrics {
  glyph: number;
  rule: number;
  gap: number;
  padY: number;
}

const SIZE_METRICS: Record<FleuronSize, FleuronMetrics> = {
  sm: { glyph: 16, rule: 56, gap: 14, padY: 16 },
  md: { glyph: 20, rule: 80, gap: 18, padY: 28 },
  lg: { glyph: 28, rule: 112, gap: 22, padY: 44 },
};

/**
 * `<Fleuron />` — a chapter / section divider that echoes the
 * `.chapter-fleuron` mark from armance.io. A single ❦ glyph rendered
 * in `--accent`, flanked by hairline rules in `--rule`.
 *
 * Purely decorative: marked `aria-hidden` so it never reaches the
 * accessibility tree. No visible strings, no i18n surface.
 */
export const Fleuron: FC<FleuronProps> = ({ size = "md", className }) => {
  const metrics = SIZE_METRICS[size];

  const rootStyle: CSSProperties = {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: `${metrics.gap}px`,
    paddingTop: `${metrics.padY}px`,
    paddingBottom: `${metrics.padY}px`,
    width: "100%",
  };

  const ruleStyle: CSSProperties = {
    flex: "0 0 auto",
    width: `${metrics.rule}px`,
    height: 0,
    borderTop: "1px solid var(--rule)",
  };

  const glyphStyle: CSSProperties = {
    flex: "0 0 auto",
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontSize: `${metrics.glyph}px`,
    lineHeight: 1,
    color: "var(--accent)",
    userSelect: "none",
  };

  const rootClassName = ["chapter-fleuron", className]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      role="separator"
      aria-hidden="true"
      data-size={size}
      className={rootClassName}
      style={rootStyle}
    >
      <span style={ruleStyle} />
      <span style={glyphStyle}>❦</span>
      <span style={ruleStyle} />
    </div>
  );
};

export default Fleuron;
