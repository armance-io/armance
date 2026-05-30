"use client";

import { useTranslation } from "react-i18next";
import { AppShell } from "@/components/visual/AppShell";
import LibraryPaneContainer from "@/components/library/LibraryPaneContainer";
import { useRouteParams } from "@/lib/routeParams";

export default function LibraryView() {
  const { pid, sid } = useRouteParams();
  const { t } = useTranslation();

  return (
    <AppShell t={t}>
      <LibraryPaneContainer pid={pid} sid={sid} />
    </AppShell>
  );
}
