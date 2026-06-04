"use client";

import { type CSSProperties, type FC, useState } from "react";
import { useTranslation } from "react-i18next";
import { LivePanelContainer } from "@/components/run/LivePanelContainer";
import { RunFlowContainer } from "@/components/run/RunFlowContainer";
import { tokens } from "@/components/_shared/armance-tokens";

export interface WorkflowRunPanelProps {
  pid: string;
  sid: string;
  workflowName: string;
  runId: string;
}

type Tab = "flow" | "report";

/**
 * Right-hand panel shown while a workflow run is active. Two tabs:
 *  - Flux: the live step-by-step run (who runs what, HITL questions).
 *  - Compte rendu: the synthesis, arguments, sources, hypotheses (LivePanel).
 * Fills its container; the container owns the (resizable) width.
 */
export const WorkflowRunPanel: FC<WorkflowRunPanelProps> = ({ pid, sid, workflowName, runId }) => {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("flow");

  const tabBar: CSSProperties = {
    display: "flex",
    flexShrink: 0,
    borderBottom: `1px solid ${tokens.rule}`,
    background: tokens.bgPaperDeep,
  };
  const tabBtn = (active: boolean): CSSProperties => ({
    flex: 1,
    padding: "12px 8px",
    border: "none",
    borderBottom: active ? `2px solid ${tokens.accent}` : "2px solid transparent",
    background: "transparent",
    color: active ? tokens.accent : tokens.inkSoft,
    fontFamily: tokens.ffSans,
    fontSize: 13,
    fontWeight: active ? 600 : 400,
    cursor: "pointer",
  });

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", minHeight: 0 }}>
      <div style={tabBar} role="tablist">
        <button role="tab" aria-selected={tab === "flow"} style={tabBtn(tab === "flow")} onClick={() => setTab("flow")}>
          {t("run:tabs.flow")}
        </button>
        <button role="tab" aria-selected={tab === "report"} style={tabBtn(tab === "report")} onClick={() => setTab("report")}>
          {t("run:tabs.report")}
        </button>
      </div>
      <div style={{ flex: 1, minHeight: 0, overflow: "auto" }} role="tabpanel">
        {tab === "flow" ? (
          <RunFlowContainer pid={pid} sid={sid} workflowName={workflowName} runId={runId} />
        ) : (
          <LivePanelContainer pid={pid} sid={sid} workflowName={workflowName} runId={runId} />
        )}
      </div>
    </div>
  );
};

export default WorkflowRunPanel;
