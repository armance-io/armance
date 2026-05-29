"use client";

import { use } from "react";
import { useTranslation } from "react-i18next";
import { AppShell } from "@/components/visual/AppShell";
import { RunDetailContainer } from "@/components/runs/RunDetailContainer";
import { WorkflowGraphContainer } from "@/components/workflow/WorkflowGraphContainer";
import { InterruptButtonContainer } from "@/components/workflow/InterruptButtonContainer";
import { RunHistoryContainer } from "@/components/workflow/RunHistoryContainer";
import { LivePanelContainer } from "@/components/run/LivePanelContainer";

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
            <InterruptButtonContainer
              pid={pid}
              sid={sid}
              workflowName={workflowName}
              runId={runId}
            />
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
    </AppShell>
  );
}
