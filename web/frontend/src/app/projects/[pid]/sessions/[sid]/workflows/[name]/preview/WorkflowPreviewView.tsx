"use client";

import { useTranslation } from "react-i18next";
import { AppShell } from "@/components/visual/AppShell";
import { EmptyShell } from "@/components/visual/EmptyState/EmptyShell";
import WorkflowGraphContainer from "@/components/workflow/WorkflowGraphContainer";
import { useRouteParams } from "@/lib/routeParams";

export default function WorkflowPreviewView() {
  const { pid, sid, name = "" } = useRouteParams();
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
        workflowName={name}
      />
    </AppShell>
  );
}
