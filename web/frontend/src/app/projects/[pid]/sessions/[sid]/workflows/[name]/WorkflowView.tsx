"use client";

import { type CSSProperties, useState } from "react";
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
import { useToast } from "@/components/_shared/Toast";
import { tokens } from "@/components/_shared/armance-tokens";

export default function WorkflowView() {
  const { pid, sid, name = "" } = useRouteParams();
  const { t } = useTranslation();
  const { toast } = useToast();
  const workflowName = name;

  const { data: activeData, refetch: refetchActive } = useQuery({
    queryKey: ["active-workflow", pid, sid],
    queryFn: () => getActiveWorkflow(pid, sid).catch(() => null),
    refetchInterval: 2000,
    enabled: Boolean(pid && sid),
  });

  const { data: workflowsData, isFetched: workflowsFetched } = useQuery({
    queryKey: ["workflows", pid, sid],
    queryFn: () => listWorkflows(pid, sid).catch(() => ({ workflows: [] })),
    enabled: Boolean(pid && sid),
  });
  const workflowExists =
    !workflowsFetched ||
    (workflowsData?.workflows ?? []).some((w) => w.name === workflowName);

  const activeRunId = activeData?.active?.run_id;
  const [launching, setLaunching] = useState(false);

  const handleLaunch = async (mode: "interactive" | "autonomous", depth: "quick" | "deep") => {
    setLaunching(true);
    try {
      const result = await launchWorkflow(pid, sid, workflowName, { mode, depth });
      toast(t("workflow:launch.started").replace("{id}", result.run_id), "success");
      refetchActive();
    } catch {
      toast(t("workflow:launch.error"), "error");
    } finally {
      setLaunching(false);
    }
  };

  const heading: CSSProperties = {
    fontFamily: tokens.ffSerif, fontSize: 24, color: tokens.ink, margin: 0, fontWeight: 500,
  };
  const sectionLabel: CSSProperties = {
    fontFamily: tokens.ffMono, fontSize: 9, letterSpacing: "0.14em",
    textTransform: "uppercase", color: tokens.inkFaint, margin: "0 0 8px",
  };

  // No AppShell `sidebar` prop: Past runs lives in-page (under the title),
  // not appended to the bottom of the global nav.
  return (
    <AppShell t={t}>
      <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
        {/* Centre */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 24, padding: `${tokens.tabPadY} ${tokens.tabPadX}`, overflow: "auto" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={heading}>{workflowName}</h3>
            {activeRunId && (
              <InterruptButtonContainer pid={pid} sid={sid} workflowName={workflowName} runId={activeRunId} />
            )}
          </div>

          {/* Past runs — under the workflow title (not the global sidebar) */}
          {workflowExists && (
            <section>
              <p style={sectionLabel}>{t("workflow:runs.title")}</p>
              <RunHistoryContainer pid={pid} sid={sid} workflowName={workflowName} />
            </section>
          )}

          <WorkflowGraphContainer pid={pid} sid={sid} workflowName={workflowName} runId={activeRunId} />
        </div>

        {/* Right panel */}
        <div style={{ width: 420, height: "100%", borderLeft: `1px solid ${tokens.rule}`, display: "flex", flexDirection: "column", overflow: "auto" }}>
          {activeRunId ? (
            <LivePanelContainer pid={pid} sid={sid} workflowName={workflowName} runId={activeRunId} />
          ) : workflowExists ? (
            <div style={{ flex: 1, overflow: "auto" }}>
              <DepthPicker workflowName={workflowName} onLaunch={handleLaunch} t={t} />
              {launching && (
                <div style={{ marginTop: 20, textAlign: "center", fontFamily: tokens.ffMono, fontSize: 13, color: tokens.accent }} data-testid="launch-status">
                  {t("workflow:launch.in_progress")}
                </div>
              )}
            </div>
          ) : (
            <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 32, gap: 12, textAlign: "center" }} data-testid="no-workflow-state">
              <div style={{ fontFamily: tokens.ffSerif, fontSize: 16, color: tokens.ink, fontWeight: 500 }}>
                {t("workflow:empty.title")}
              </div>
              <div style={{ fontFamily: tokens.ffSans, fontSize: 13, color: tokens.inkSoft, maxWidth: 260, lineHeight: 1.5 }}>
                {t("workflow:empty.hint")}
              </div>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
