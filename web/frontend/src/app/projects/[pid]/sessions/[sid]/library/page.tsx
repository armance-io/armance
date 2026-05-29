"use client";

import { use } from "react";
import { useTranslation } from "react-i18next";
import { AppShell } from "@/components/visual/AppShell";
import { EmptyShell } from "@/components/visual/EmptyState/EmptyShell";
import LibraryPaneContainer from "@/components/library/LibraryPaneContainer";

interface LibraryPageProps {
  params: Promise<{
    pid: string;
    sid: string;
  }>;
}

export default function LibraryPage({ params }: LibraryPageProps) {
  const { pid, sid } = use(params);
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
