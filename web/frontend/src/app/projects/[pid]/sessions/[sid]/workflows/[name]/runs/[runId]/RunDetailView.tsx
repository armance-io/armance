"use client";

import { useQuery } from "@tanstack/react-query";
import { RunDetailContainer } from "@/components/runs/RunDetailContainer";
import { WorkflowGraphContainer } from "@/components/workflow/WorkflowGraphContainer";
import { InterruptButtonContainer } from "@/components/workflow/InterruptButtonContainer";
import { RunHistoryContainer } from "@/components/workflow/RunHistoryContainer";
import { LivePanelContainer } from "@/components/run/LivePanelContainer";
import { getActiveWorkflow } from "@/lib/api";
import { useRouteParams } from "@/lib/routeParams";

export default function RunDetailView() {
  const { pid, sid, name = "", runId = "" } = useRouteParams();

  const workflowName = name;

  // 1. Fetch active workflow state dynamically with 2-second polling interval (D-WIRE.8)
  const { data: activeData } = useQuery({
    queryKey: ["active-workflow", pid, sid],
    queryFn: () => getActiveWorkflow(pid, sid).catch(() => null),
    refetchInterval: 2000,
    enabled: Boolean(pid && sid),
  });

  const activeRunId = activeData?.active?.run_id;

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      {/* Sidebar / Left Column for Run history */}
      <div style={{
        width: "280px",
        flexShrink: 0,
        borderRight: "1px solid var(--rule, #d6c8ad)",
        display: "flex",
        flexDirection: "column",
        height: "100%",
        background: "var(--bg-paper, #f4ede0)",
        padding: "16px",
        gap: "16px",
      }}>
        <div style={{
          fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
          fontSize: "18px",
          fontWeight: 600,
          color: "var(--ink, #2a2520)",
          paddingBottom: "8px",
          borderBottom: "1px solid var(--rule, #d6c8ad)",
        }}>
          {workflowName}
        </div>
        <div style={{ flex: 1, minHeight: 0 }}>
          <RunHistoryContainer
            pid={pid}
            sid={sid}
            workflowName={workflowName}
          />
        </div>
      </div>

      <div style={{ flex: 1, display: "flex", height: "100%", overflow: "hidden" }}>
        {/* Left Column */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "24px", padding: "24px", overflow: "auto" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={{
              fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
              fontSize: "22px",
              color: "var(--ink, #2a2520)",
              margin: 0,
            }}>
              Run details — {runId}
            </h3>
            {activeRunId === runId && (
              <InterruptButtonContainer
                pid={pid}
                sid={sid}
                workflowName={workflowName}
                runId={runId}
              />
            )}
          </div>
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

        {/* Right Column */}
        <LivePanelContainer
          pid={pid}
          sid={sid}
          workflowName={workflowName}
          runId={runId}
        />
      </div>
    </div>
  );
}
