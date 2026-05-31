"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/visual/AppShell";
import { DepthPicker } from "@/components/workflow/DepthPicker";
import { WorkflowGraphContainer } from "@/components/workflow/WorkflowGraphContainer";
import { InterruptButtonContainer } from "@/components/workflow/InterruptButtonContainer";
import { RunHistoryContainer } from "@/components/workflow/RunHistoryContainer";
import { LivePanelContainer } from "@/components/run/LivePanelContainer";
import { launchWorkflow, getActiveWorkflow, listWorkflows } from "@/lib/api";
import { useRouteParams } from "@/lib/routeParams";

export default function WorkflowView() {
  const { pid, sid, name = "" } = useRouteParams();
  const { t } = useTranslation();
  const [status, setStatus] = useState<string | null>(null);

  const workflowName = name;

  // 1. Fetch active workflow state dynamically with 2-second polling interval (D-WIRE.8)
  const { data: activeData, refetch: refetchActive } = useQuery({
    queryKey: ["active-workflow", pid, sid],
    queryFn: () => getActiveWorkflow(pid, sid).catch(() => null),
    refetchInterval: 2000,
    enabled: Boolean(pid && sid),
  });

  // 2. Check if this workflow actually exists on disk
  const { data: workflowsData, isFetched: workflowsFetched } = useQuery({
    queryKey: ["workflows", pid, sid],
    queryFn: () => listWorkflows(pid, sid).catch(() => ({ workflows: [] })),
    enabled: Boolean(pid && sid),
  });
  // Only hide the launcher once we have a confirmed empty list (not during loading)
  const workflowExists =
    !workflowsFetched ||
    (workflowsData?.workflows ?? []).some((w) => w.name === workflowName);

  const activeRunId = activeData?.active?.run_id;

  const handleLaunch = async (
    mode: "interactive" | "autonomous",
    depth: "quick" | "deep"
  ) => {
    try {
      setStatus("launching...");
      const result = await launchWorkflow(pid, sid, workflowName, { mode, depth });
      setStatus(`Run launched: ${result.run_id}`);
      refetchActive(); // Refresh active workflow status immediately
    } catch (err) {
      console.error(err);
      setStatus("Error launching run.");
    }
  };

  return (
    <AppShell
      sidebar={
        <div style={{ display: "flex", flexDirection: "column", gap: "16px", padding: "16px", height: "100%" }}>
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
          <RunHistoryContainer
            pid={pid}
            sid={sid}
            workflowName={workflowName}
          />
        </div>
      }
      t={t}
    >
      <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
        {/* Centre Content */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "24px", padding: "24px", overflow: "auto" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={{
              fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
              fontSize: "22px",
              color: "var(--ink, #2a2520)",
              margin: 0,
            }}>
              {workflowName}
            </h3>
            {activeRunId && (
              <InterruptButtonContainer
                pid={pid}
                sid={sid}
                workflowName={workflowName}
                runId={activeRunId}
              />
            )}
          </div>
          <WorkflowGraphContainer
            pid={pid}
            sid={sid}
            workflowName={workflowName}
            runId={activeRunId}
          />
        </div>

        {/* Right Panel */}
        <div style={{ width: "420px", height: "100%", borderLeft: "1px solid var(--rule, #d6c8ad)", display: "flex", flexDirection: "column", overflow: "auto" }}>
          {activeRunId ? (
            <LivePanelContainer
              pid={pid}
              sid={sid}
              workflowName={workflowName}
              runId={activeRunId}
            />
          ) : workflowExists ? (
            <div style={{ flex: 1, overflow: "auto" }}>
              <DepthPicker
                workflowName={workflowName}
                onLaunch={handleLaunch}
                t={t}
              />
              {status && (
                <div
                  style={{
                    marginTop: "20px",
                    textAlign: "center",
                    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
                    fontSize: "14px",
                    color: "var(--accent, #6b4f8a)",
                  }}
                  data-testid="launch-status"
                >
                  {status}
                </div>
              )}
            </div>
          ) : (
            <div
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                padding: "32px",
                gap: "12px",
                textAlign: "center",
              }}
              data-testid="no-workflow-state"
            >
              <div style={{
                fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
                fontSize: "16px",
                color: "var(--ink, #2a2520)",
                fontWeight: 500,
              }}>
                {t("workflow:empty.title")}
              </div>
              <div style={{
                fontFamily: "var(--ff-sans, sans-serif)",
                fontSize: "13px",
                color: "var(--ink-soft, #5b5145)",
                maxWidth: "260px",
                lineHeight: 1.5,
              }}>
                {t("workflow:empty.hint")}
              </div>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
