import { type FC } from "react";

import { EmptyShell } from "./EmptyShell";

/* ─── Types ──────────────────────────────────────────────────────────────── */

export interface EmptySessionProps {
  /**
   * i18n accessor. Keys consumed:
   *   visual:empty.session.title
   *   visual:empty.session.hint
   *   visual:empty.session.cta   (only when `onCta` is provided — wire the key
   *                                in locale files when surfacing a CTA)
   */
  t: (key: string) => string;
  /** Optional action — typically "drop a document" or "show prompts". */
  onCta?: () => void;
}

/* ─── Component ──────────────────────────────────────────────────────────── */

/**
 * `<EmptySession />` — chat-pane state shown before the first message.
 */
export const EmptySession: FC<EmptySessionProps> = ({ t, onCta }) => (
  <EmptyShell
    title={t("visual:empty.session.title")}
    hint={t("visual:empty.session.hint")}
    ctaLabel={onCta ? t("visual:empty.session.cta") : undefined}
    onCta={onCta}
  />
);

export default EmptySession;
