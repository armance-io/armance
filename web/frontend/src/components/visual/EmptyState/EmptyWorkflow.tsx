import { type FC } from "react";

import { EmptyShell } from "./EmptyShell";

/* ─── Types ──────────────────────────────────────────────────────────────── */

export interface EmptyWorkflowProps {
  /**
   * i18n accessor. Keys consumed:
   *   visual:empty.workflow.title
   *   visual:empty.workflow.hint
   *   visual:empty.workflow.cta   (only when `onCta` is provided — wire the key
   *                                 in locale files when surfacing a CTA)
   */
  t: (key: string) => string;
  /** Optional action — typically "start a workflow". */
  onCta?: () => void;
}

/* ─── Component ──────────────────────────────────────────────────────────── */

/**
 * `<EmptyWorkflow />` — pane state shown when no workflow is running.
 */
export const EmptyWorkflow: FC<EmptyWorkflowProps> = ({ t, onCta }) => (
  <EmptyShell
    title={t("visual:empty.workflow.title")}
    hint={t("visual:empty.workflow.hint")}
    ctaLabel={onCta ? t("visual:empty.workflow.cta") : undefined}
    onCta={onCta}
  />
);

export default EmptyWorkflow;
