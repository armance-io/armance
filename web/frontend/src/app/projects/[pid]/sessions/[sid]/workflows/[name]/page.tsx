"use client";

import { use, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/visual/AppShell";
import { DepthPicker } from "@/components/workflow/DepthPicker";
import { WorkflowGraphContainer } from "@/components/workflow/WorkflowGraphContainer";
import { InterruptButtonContainer } from "@/components/workflow/InterruptButtonContainer";
import { RunHistoryContainer } from "@/components/workflow/RunHistoryContainer";
import { LivePanelContainer } from "@/components/run/LivePanelContainer";
import { launchWorkflow, getActiveWorkflow } from "@/lib/api";

interface WorkflowPageProps {
  params: Promise<{
    pid: string;
    sid: string;
    name: string;
  }>;
}

export default function WorkflowPage({ params }: WorkflowPageProps) {
  const { pid, sid, name } = use(params);
  const { t } = useTranslation();
  const [status, setStatus] = useState<string | null>(null);

  const workflowName = decodeURIComponent(name);

  // 1. Fetch active workflow state dynamically with 2-second polling interval (D-WIRE.8)
  const { data: activeData, refetch: refetchActive } = useQuery({
    queryKey: ["active-workflow", pid, sid],
    queryFn: () => getActiveWorkflow(pid, sid).catch(() => null),
    refetchInterval: 2000,
  });

  const activeRunId = activeData?.active?.run_id;

  // Custom translation function to handle missing keys in V2 scaffold safely
  const customT = (key: string): string => {
    if (key === "workflow:picker.quick_title") return "A quick perspective";
    if (key === "workflow:picker.quick_desc") return "Rapid verification of primary assumptions using key benchmarks.";
    if (key === "workflow:picker.deep_title") return "A thorough, challenged analysis";
    if (key === "workflow:picker.deep_desc") return "Rigorous evaluation challenging all assertions through structural debate.";
    if (key === "workflow:picker.mode_interactive") return "interactive";
    if (key === "workflow:picker.mode_autonomous") return "autonomous";
    if (key === "workflow:picker.hint_interactive") return "Mona will ask for your guidance at key decision thresholds.";
    if (key === "workflow:picker.hint_autonomous") return "Mona operates autonomous checkpoints to deliver the synthesis.";
    if (key === "workflow:picker.launch") return "Launch";
    return t(key);
  };

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
          ) : (
            <div style={{ flex: 1, overflow: "auto" }}>
              <DepthPicker
                workflowName={workflowName}
                onLaunch={handleLaunch}
                t={customT}
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
          )}
        </div>
      </div>
    </AppShell>
  );
}

