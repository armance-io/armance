"use client";

import { type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { AppShell } from "@/components/visual/AppShell";

/**
 * Persistent shell for every project route (sessions, workflows, library,
 * deliverables, admin). AppShell lives here — in a layout — so switching L0
 * tabs swaps only this layout's children (the `main` content), never the
 * header or sidebar. Pages render their content only; they must NOT wrap
 * themselves in AppShell.
 */
export default function ProjectLayout({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  return <AppShell t={t}>{children}</AppShell>;
}
