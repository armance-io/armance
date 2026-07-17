"use client";

import { type FC } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { WorkflowGraph } from "./WorkflowGraph";
import { getWorkflow } from "@/lib/api";
import { useLiveManifest } from "@/lib/useLiveManifest";
import type { RawNode } from "@/lib/graphLayout";
import type { CrucibleStage } from "@/components/workflow/stepNodeStage";

interface StepRecord {
  id: string;
  status:
    | "queued"
    | "working"
    | "completed"
    | "failed"
    | "cancelled"
    | "skipped"
    | "provided";
  agent?: string;
  duration_ms?: number;
  started_at?: string;
  ended_at?: string;
  /** Creuset fields written by the runner into manifest.json. */
  stage?: string;
  family?: string;
  tokens_in?: number;
  tokens_out?: number;
  cost_usd?: number;
}

export interface WorkflowGraphContainerProps {
  pid: string;
  sid: string;
  workflowName: string;
  runId?: string | undefined;
}

export const WorkflowGraphContainer: FC<WorkflowGraphContainerProps> = ({
  pid,
  sid,
  workflowName,
  runId,
}) => {
  const { t } = useTranslation();

  // 1. Fetch the workflow YAML configuration.
  const { data: workflowData } = useQuery({
    queryKey: ["workflow", pid, sid, workflowName],
    queryFn: () => getWorkflow(pid, sid, workflowName).catch(() => null),
  });

  // 2. Poll active run manifest if runId is supplied.
  const { data: runData } = useLiveManifest(
    pid,
    sid,
    workflowName,
    runId || ""
  );

  // Parse live manifest step updates (D.10)
  const runManifest = runData && runData["manifest.json"]
    ? JSON.parse(runData["manifest.json"])
    : null;

  // The backend returns the real graph under `graph.{nodes,edges}`. Nodes
  // carry {step_id, kind, role} but no run status until a run manifest
  // exists — default to "queued". No placeholder fixture: while the
  // workflow loads (or fails to), the graph shows its designed empty state
  // instead of three fake steps.
  const baseNodes = (workflowData?.graph?.nodes as RawNode[] | undefined) ?? [];
  const mergedNodes = baseNodes.map((n: RawNode) => {
    const stepRecord = runManifest?.steps?.find((s: StepRecord) => s.id === n.id);
    const stepStatus = stepRecord ? stepRecord.status : (n.data.status ?? "queued");
    const stepDuration = stepRecord ? stepRecord.duration_ms : n.data.duration_ms;
    const startedAt = stepRecord ? stepRecord.started_at : n.data.started_at;
    const endedAt = stepRecord ? stepRecord.ended_at : n.data.ended_at;

    return {
      ...n,
      data: {
        ...n.data,
        status: stepStatus,
        agent: stepRecord?.agent ?? undefined,
        duration_ms: stepDuration,
        started_at: startedAt,
        ended_at: endedAt,
        // Creuset: prefer the definition's stage (graph data), fall back to
        // the manifest record. Family/cost only exist once a run speaks.
        stage: ((n.data.stage ?? stepRecord?.stage) ?? null) as CrucibleStage | null,
        family: stepRecord?.family ?? null,
        tokens_in: stepRecord?.tokens_in ?? null,
        tokens_out: stepRecord?.tokens_out ?? null,
        cost_usd: stepRecord?.cost_usd ?? null,
        provided: stepRecord?.status === "provided",
      },
    };
  });

  const edges = workflowData?.graph?.edges ?? [];

  return (
    <div
      style={{
        // Viewport-scaled: 18-step DAGs squeezed into a fixed 400px strip
        // were unreadable after fitView. Kept as a bounded height (not
        // flex:1) — a growing flex child overlapped the content below in
        // the RunDetail column.
        height: "clamp(420px, 55vh, 720px)",
        width: "100%",
        border: "1px solid var(--rule, #d6c8ad)",
        borderRadius: "2px",
        overflow: "hidden",
        display: "flex",
      }}
      data-testid="workflow-graph-container"
    >
      <WorkflowGraph
        nodes={mergedNodes}
        edges={edges}
        t={t}
      />
    </div>
  );
};

export default WorkflowGraphContainer;
