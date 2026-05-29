"use client";

import { type FC, useState, useCallback, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { WorkflowGraph } from "./WorkflowGraph";
import { getWorkflow } from "@/lib/api";
import { useLiveManifest } from "@/lib/useLiveManifest";
import { useEventStream, type SseEvent } from "@/lib/sse";
import type { RawNode } from "@/lib/graphLayout";

interface StepRecord {
  id: string;
  status: "queued" | "working" | "completed" | "failed" | "cancelled" | "skipped";
  duration_ms?: number;
  started_at?: string;
  ended_at?: string;
}

export interface WorkflowGraphContainerProps {
  pid: string;
  sid: string;
  workflowName: string;
  runId?: string;
}

export const WorkflowGraphContainer: FC<WorkflowGraphContainerProps> = ({
  pid,
  sid,
  workflowName,
  runId,
}) => {
  const { t } = useTranslation();
  const [streamingSteps, setStreamingSteps] = useState<Record<string, boolean>>({});
  const timeoutsRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  // 1. Fetch the workflow YAML configuration Fallback
  const { data: workflowData } = useQuery({
    queryKey: ["workflow", pid, sid, workflowName],
    queryFn: () => getWorkflow(pid, sid, workflowName).catch(() => null),
  });

  // 2. Poll active run manifest if runId is supplied
  const { data: runData } = useLiveManifest(
    pid,
    sid,
    workflowName,
    runId || ""
  );

  // 3. Listen to agent stream events for visual StepNode pulse (D.12)
  const handleSseEvent = useCallback((evt: SseEvent) => {
    const stepId = evt.data.step_id as string | undefined;
    if (!stepId) return;

    if (evt.name === "agent_streaming_started" || evt.name === "agent_streaming") {
      setStreamingSteps((prev) => ({ ...prev, [stepId]: true }));
      
      // Debounce streaming: clear existing timeout and reset to flip false in 1.5s of no tokens
      if (timeoutsRef.current[stepId]) {
        clearTimeout(timeoutsRef.current[stepId]);
      }
      
      timeoutsRef.current[stepId] = setTimeout(() => {
        setStreamingSteps((prev) => ({ ...prev, [stepId]: false }));
      }, 1500);
    } else if (evt.name === "agent_streaming_end") {
      if (timeoutsRef.current[stepId]) {
        clearTimeout(timeoutsRef.current[stepId]);
      }
      timeoutsRef.current[stepId] = setTimeout(() => {
        setStreamingSteps((prev) => ({ ...prev, [stepId]: false }));
      }, 1500);
    }
  }, []);

  useEventStream(pid, sid, handleSseEvent);

  // 4. Default topological 3-node fixture (LR connections) as safe preview fallback
  const fallbackNodes = [
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

  const fallbackEdges = [
    { id: "step-1->step-2", source: "step-1", target: "step-2" },
    { id: "step-2->step-3", source: "step-2", target: "step-3" },
  ];

  // Parse live manifest step updates (D.10, D.11)
  const runManifest = runData && runData["manifest.json"]
    ? JSON.parse(runData["manifest.json"])
    : null;

  const mergedNodes = ((workflowData?.nodes as RawNode[] | undefined) || fallbackNodes).map((n: RawNode) => {
    const stepRecord = runManifest?.steps?.find((s: StepRecord) => s.id === n.id);
    const stepStatus = stepRecord ? stepRecord.status : n.data.status;
    const stepDuration = stepRecord ? stepRecord.duration_ms : n.data.duration_ms;
    const startedAt = stepRecord ? stepRecord.started_at : n.data.started_at;
    const endedAt = stepRecord ? stepRecord.ended_at : n.data.ended_at;

    return {
      ...n,
      data: {
        ...n.data,
        status: stepStatus,
        duration_ms: stepDuration,
        started_at: startedAt,
        ended_at: endedAt,
        streaming: streamingSteps[n.id] || false,
      },
    };
  });

  const edges = workflowData?.edges || fallbackEdges;

  return (
    <div
      style={{
        height: "400px",
        width: "100%",
        border: "1px solid var(--rule, #d6c8ad)",
        borderRadius: "4px",
        overflow: "hidden",
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
