"use client";

import { use } from "react";
import { useTranslation } from "react-i18next";
import { AppShell } from "@/components/visual/AppShell";
import { EmptyShell } from "@/components/visual/EmptyState/EmptyShell";
import WorkflowGraphContainer from "@/components/workflow/WorkflowGraphContainer";

interface WorkflowPreviewPageProps {
  params: Promise<{
    pid: string;
    sid: string;
    name: string;
  }>;
}

export default function WorkflowPreviewPage({ params }: WorkflowPreviewPageProps) {
  const { pid, sid, name } = use(params);
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
      <WorkflowGraphContainer
        pid={pid}
        sid={sid}
        workflowName={decodeURIComponent(name)}
      />
    </AppShell>
  );
}
