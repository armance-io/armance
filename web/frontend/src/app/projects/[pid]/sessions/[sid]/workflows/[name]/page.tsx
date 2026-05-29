"use client";

import { use, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/visual/AppShell";
import { EmptyShell } from "@/components/visual/EmptyState/EmptyShell";
import { DepthPicker } from "@/components/workflow/DepthPicker";
import { WorkflowGraphContainer } from "@/components/workflow/WorkflowGraphContainer";
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

  // 1. Fetch active workflow state dynamically (D.10)
  const { data: activeData, refetch: refetchActive } = useQuery({
    queryKey: ["active-workflow", pid, sid],
    queryFn: () => getActiveWorkflow(pid, sid).catch(() => null),
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
      refetchActive(); // Refresh active workflow status
    } catch (err) {
      console.error(err);
      setStatus("Error launching run.");
    }
  };

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
      <div style={{ padding: "24px", color: "var(--ink-soft)" }}>
        {activeRunId ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
            <h3 style={{
              fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
              fontSize: "22px",
              color: "var(--ink, #2a2520)",
              margin: 0,
            }}>
              {workflowName} — Live Graph
            </h3>
            <WorkflowGraphContainer
              pid={pid}
              sid={sid}
              workflowName={workflowName}
              runId={activeRunId}
            />
          </div>
        ) : (
          <>
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
          </>
        )}
      </div>
    </AppShell>
  );
}
