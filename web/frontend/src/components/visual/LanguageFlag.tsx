"use client";

// Monochrome, palette-tinted flag glyphs for the setup language picker.
//
// We deliberately avoid flag emoji (🇬🇧 …): Windows (Segoe UI Emoji) refuses to
// render region-indicator sequences as flags, showing "GB"/"FR" or tofu instead.
// These geometric SVGs render identically on every platform and, drawn with
// `currentColor`, tint to the Belle-Époque palette (DESIGN.md §2/§6 — no garish
// colour). The selected card sets `color` to --accent; otherwise --ink-soft.

import type { CSSProperties, ReactElement } from "react";

type FlagId = "en" | "fr" | "es" | "de" | "zh" | "ja";

// 32×22 viewBox, fine-stroke + soft fills, single ink colour via currentColor.
// Each is a restrained, recognisable abstraction — vertical/horizontal bands or
// a central emblem — never literal heraldry.
const FLAGS: Record<FlagId, ReactElement> = {
  // Union-style: cross + saltire, drawn as thin rules.
  en: (
    <>
      <rect x="0.5" y="0.5" width="31" height="21" rx="1.5" fill="none" strokeWidth="1" />
      <path d="M0.5 0.5 L31.5 21.5 M31.5 0.5 L0.5 21.5" strokeWidth="1" opacity="0.5" />
      <path d="M16 0.5 V21.5 M0.5 11 H31.5" strokeWidth="2.4" />
    </>
  ),
  // Three vertical bands (left filled, right hatched).
  fr: (
    <>
      <rect x="0.5" y="0.5" width="31" height="21" rx="1.5" fill="none" strokeWidth="1" />
      <rect x="0.5" y="0.5" width="10.3" height="21" opacity="0.85" />
      <rect x="21.2" y="0.5" width="10.3" height="21" opacity="0.35" />
    </>
  ),
  // Three horizontal bands, wide centre.
  es: (
    <>
      <rect x="0.5" y="0.5" width="31" height="21" rx="1.5" fill="none" strokeWidth="1" />
      <rect x="0.5" y="0.5" width="31" height="5.5" opacity="0.4" />
      <rect x="0.5" y="16" width="31" height="5.5" opacity="0.4" />
      <rect x="11" y="9" width="10" height="4" opacity="0.85" />
    </>
  ),
  // Three horizontal bands, descending weight.
  de: (
    <>
      <rect x="0.5" y="0.5" width="31" height="21" rx="1.5" fill="none" strokeWidth="1" />
      <rect x="0.5" y="0.5" width="31" height="7" opacity="0.85" />
      <rect x="0.5" y="7.5" width="31" height="7" opacity="0.5" />
      <rect x="0.5" y="14.5" width="31" height="7" opacity="0.25" />
    </>
  ),
  // Central star cluster.
  zh: (
    <>
      <rect x="0.5" y="0.5" width="31" height="21" rx="1.5" fill="none" strokeWidth="1" />
      <path
        d="M11 6 l1.3 3.4 3.6 0.2 -2.8 2.3 1 3.5 -3.1 -2 -3.1 2 1 -3.5 -2.8 -2.3 3.6 -0.2 Z"
        strokeWidth="0.6"
      />
      <circle cx="20" cy="6" r="1" />
      <circle cx="22.5" cy="9" r="1" />
      <circle cx="22.5" cy="13" r="1" />
      <circle cx="20" cy="16" r="1" />
    </>
  ),
  // Central disc.
  ja: (
    <>
      <rect x="0.5" y="0.5" width="31" height="21" rx="1.5" fill="none" strokeWidth="1" />
      <circle cx="16" cy="11" r="6.2" opacity="0.85" />
    </>
  ),
};

export function LanguageFlag({ id, size = 26 }: { id: FlagId; size?: number }) {
  const style: CSSProperties = { display: "block", color: "inherit" };
  return (
    <svg
      width={size}
      height={(size * 22) / 32}
      viewBox="0 0 32 22"
      fill="currentColor"
      stroke="currentColor"
      style={style}
      aria-hidden="true"
      focusable="false"
    >
      {FLAGS[id]}
    </svg>
  );
}
