"use client";

import { useTranslation } from "react-i18next";
import { AppShell } from "@/components/visual/AppShell";
import { EmptyShell } from "@/components/visual/EmptyState/EmptyShell";
import LibraryPaneContainer from "@/components/library/LibraryPaneContainer";
import { useRouteParams } from "@/lib/routeParams";

export default function LibraryView() {
  const { pid, sid } = useRouteParams();
  const { t } = useTranslation();

  return (
    <AppShell
      sidebar={
        <EmptyShell
          title={t("visual:empty.shell.title")}
          hint={t("visual:empty.shell.hint")}
        />
      }
      t={t}
    >
      <LibraryPaneContainer pid={pid} sid={sid} />
    </AppShell>
  );
}
