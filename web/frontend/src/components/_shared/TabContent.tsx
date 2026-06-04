"use client";

import { type CSSProperties, type FC, type ReactNode } from "react";
import { tokens } from "./armance-tokens";

/**
 * Uniform content shell for every tab / page body.
 *
 * One source of truth for the top padding and surface, so Library, Settings,
 * Workflows, etc. all start the content at the same vertical offset and share
 * the same paper background (fixes per-tab spacing/background drift).
 */
export interface TabContentProps {
  children: ReactNode;
  /** Max readable width; `null` lets the content fill the area (e.g. chat). */
  maxWidth?: number | null;
  /** Drop the card background (e.g. full-bleed surfaces). */
  bare?: boolean;
  style?: CSSProperties;
  "data-testid"?: string;
}

export const TabContent: FC<TabContentProps> = ({
  children,
  maxWidth = 900,
  bare = false,
  style,
  ...rest
}) => {
  const base: CSSProperties = {
    padding: `${tokens.tabPadY} ${tokens.tabPadX}`,
    background: bare ? "transparent" : tokens.bgPaper,
    color: tokens.ink,
    fontFamily: tokens.ffSans,
    width: "100%",
    height: "100%",
    overflow: "auto",
    ...(maxWidth ? { maxWidth, marginInline: "auto" } : {}),
    ...style,
  };
  return (
    <div style={base} {...rest}>
      {children}
    </div>
  );
};

export default TabContent;
