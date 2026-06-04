"use client";

import { type CSSProperties, type FC } from "react";
import { tokens } from "./armance-tokens";

/**
 * The single "something is happening" indicator across the app — a small
 * accent dot with the calm pulse the live-logs badge uses. Reuse everywhere
 * (agent thinking, live logs, indexing…) so progress always looks the same.
 */
export interface PulseDotProps {
  size?: number;
  color?: string;
  /** Pulse while true; steady (no animation) when false. */
  active?: boolean;
  style?: CSSProperties;
}

export const PulseDot: FC<PulseDotProps> = ({ size = 7, color, active = true, style }) => (
  <span
    aria-hidden="true"
    style={{
      width: size,
      height: size,
      borderRadius: "50%",
      background: color ?? tokens.accent,
      flexShrink: 0,
      display: "inline-block",
      animation: active ? "armance-pulse-dot 1.2s ease-in-out infinite alternate" : "none",
      ...style,
    }}
  />
);

export default PulseDot;
