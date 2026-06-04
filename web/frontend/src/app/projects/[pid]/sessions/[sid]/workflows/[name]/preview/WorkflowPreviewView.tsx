"use client";

import WorkflowGraphContainer from "@/components/workflow/WorkflowGraphContainer";
import { useRouteParams } from "@/lib/routeParams";

export default function WorkflowPreviewView() {
  const { pid, sid, name = "" } = useRouteParams();

  return (
    <WorkflowGraphContainer
      pid={pid}
      sid={sid}
      workflowName={name}
    />
  );
}
