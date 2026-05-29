"use client";

import { type FC } from "react";
import { useTranslation } from "react-i18next";
import { WorkflowGraph } from "./WorkflowGraph";

export interface WorkflowGraphContainerProps {
  pid: string;
  sid: string;
  workflowName: string;
}

export const WorkflowGraphContainer: FC<WorkflowGraphContainerProps> = () => {
  const { t } = useTranslation();

  // Static fixture for D-WIRE.1 preview page
  // TODO: wire to getWorkflow once backend endpoints are fully integrated (referencing D-WIRE-BACKEND)
  const nodes = [
    {
      id: "step-1",
      data: {
        step_id: "step-1",
        role: "recruiter",
        status: "completed" as const,
        duration_ms: 1500,
      },
    },
    {
      id: "step-2",
      data: {
        step_id: "step-2",
        role: "judge",
        status: "working" as const,
        streaming: true,
      },
    },
    {
      id: "step-3",
      data: {
        step_id: "step-3",
        role: "specialist",
        status: "queued" as const,
      },
    },
  ];

  const edges = [
    { id: "step-1->step-2", source: "step-1", target: "step-2" },
    { id: "step-2->step-3", source: "step-2", target: "step-3" },
  ];

  return (
    <div style={{ height: "400px", width: "100%", border: "1px solid var(--rule, #d6c8ad)" }} data-testid="workflow-graph-preview">
      <WorkflowGraph
        nodes={nodes}
        edges={edges}
        t={t}
      />
    </div>
  );
};

export default WorkflowGraphContainer;
