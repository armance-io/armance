"use client";

import { use } from "react";
import { useTranslation } from "react-i18next";
import { AppShell } from "@/components/visual/AppShell";
import { EmptyShell } from "@/components/visual/EmptyState/EmptyShell";
import { RunDetailContainer } from "@/components/runs/RunDetailContainer";
import { WorkflowGraphContainer } from "@/components/workflow/WorkflowGraphContainer";

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

  const workflowName = decodeURIComponent(name);

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
      <div style={{ display: "flex", flexDirection: "column", gap: "24px", padding: "24px", height: "100%", overflow: "auto" }}>
        <WorkflowGraphContainer
          pid={pid}
          sid={sid}
          workflowName={workflowName}
          runId={runId}
        />
        <RunDetailContainer
          pid={pid}
          sid={sid}
          workflowName={workflowName}
          runId={runId}
        />
      </div>
    </AppShell>
  );
}
