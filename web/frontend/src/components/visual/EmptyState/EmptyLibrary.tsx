import { type FC } from "react";

import { EmptyShell } from "./EmptyShell";

/* ─── Types ──────────────────────────────────────────────────────────────── */

export interface EmptyLibraryProps {
  /**
   * i18n accessor. Keys consumed:
   *   visual:empty.library.title
   *   visual:empty.library.hint
   *   visual:empty.library.cta   (only when `onCta` is provided)
   */
  t: (key: string) => string;
  /** Optional action — typically "import a file". */
  onCta?: () => void;
}

/* ─── Component ──────────────────────────────────────────────────────────── */

/**
 * `<EmptyLibrary />` — pane state shown when `.armance/docs` is empty.
 */
export const EmptyLibrary: FC<EmptyLibraryProps> = ({ t, onCta }) => (
  <EmptyShell
    title={t("visual:empty.library.title")}
    hint={t("visual:empty.library.hint")}
    ctaLabel={onCta ? t("visual:empty.library.cta") : undefined}
    onCta={onCta}
  />
);

export default EmptyLibrary;
