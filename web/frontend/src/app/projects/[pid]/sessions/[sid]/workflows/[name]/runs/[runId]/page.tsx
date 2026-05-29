"use client";

import { use } from "react";
import { useTranslation } from "react-i18next";
import { AppShell } from "@/components/visual/AppShell";
import { EmptyShell } from "@/components/visual/EmptyState/EmptyShell";
import RunDetailContainer from "@/components/runs/RunDetailContainer";

interface RunDetailPageProps {
  params: Promise<{
    pid: string;
    sid: string;
    name: string;
    runId: string;
  }>;
}

export default function RunDetailPage({ params }: RunDetailPageProps) {
  const { pid, sid, name, runId } = use(params);
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
      <RunDetailContainer
        pid={pid}
        sid={sid}
        workflowName={decodeURIComponent(name)}
        runId={runId}
      />
    </AppShell>
  );
}
