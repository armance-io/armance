"use client";

import { type CSSProperties, useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { useEventStream, type SseEvent } from "@/lib/sse";
import { DepthPicker } from "@/components/workflow/DepthPicker";
import { WorkflowsList } from "./WorkflowsList";
import { WorkflowGraphContainer } from "@/components/workflow/WorkflowGraphContainer";
import { InterruptButtonContainer } from "@/components/workflow/InterruptButtonContainer";
import { RunHistoryContainer } from "@/components/workflow/RunHistoryContainer";
import { WorkflowRunPanel } from "@/components/workflow/WorkflowRunPanel";
import { useResizableWidth } from "@/lib/useResizableWidth";
import { launchWorkflow, getActiveWorkflow, getWorkflowEstimate, listWorkflows } from "@/lib/api";
import { useRouteParams } from "@/lib/routeParams";
import { useToast } from "@/components/_shared/Toast";
import { tokens } from "@/components/_shared/armance-tokens";

export default function WorkflowView() {
  const { pid, sid, name = "" } = useRouteParams();
  const { t } = useTranslation();
  const { toast } = useToast();
  const workflowName = name;

  // No specific workflow selected (sidebar "Workflows" → /workflows/_) → show
  // the index of workflows the user designed with Kim. Picking one routes here
  // again with a real name and renders its detail below.
  const noSelection = workflowName === "" || workflowName === "_";

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

  // Pre-run cost estimates (both depths — the picker switches locally).
  const { data: estimateQuick } = useQuery({
    queryKey: ["wf-estimate", pid, sid, workflowName, "quick"],
    queryFn: () => getWorkflowEstimate(pid, sid, workflowName, "quick").catch(() => null),
    enabled: Boolean(pid && sid && !noSelection),
  });
  const { data: estimateDeep } = useQuery({
    queryKey: ["wf-estimate", pid, sid, workflowName, "deep"],
    queryFn: () => getWorkflowEstimate(pid, sid, workflowName, "deep").catch(() => null),
    enabled: Boolean(pid && sid && !noSelection),
  });

  const activeRunId = activeData?.active?.run_id;
  const [launching, setLaunching] = useState(false);
  const [launchResult, setLaunchResult] = useState<string | null>(null);
  const [blockedReason, setBlockedReason] = useState<string | null>(null);

  // The launch POST returns 202 before the pre-run health gate runs (in a
  // detached task). When that gate blocks (unhealthy agents) the backend
  // emits `workflow.blocked` — surface it so the click is never a silent no-op.
  const handleSse = useCallback(
    (evt: SseEvent) => {
      if (evt.name !== "workflow.blocked") return;
      const attrs = (evt.data.attributes ?? {}) as Record<string, unknown>;
      const message =
        (attrs.message as string) || t("workflow:launch.blocked_fallback");
      setLaunching(false);
      setBlockedReason(message);
      toast(message, "error");
    },
    [t, toast],
  );
  useEventStream(pid, sid, handleSse);

  // The right panel is drag-resizable (left-edge handle) and remembers its width.
  const panel = useResizableWidth({
    storageKey: "armance.workflow-panel-width",
    initial: 420,
    min: 320,
    max: 720,
    edge: "left",
  });

  const handleLaunch = async (mode: "interactive" | "autonomous", depth: "quick" | "deep") => {
    setLaunching(true);
    setLaunchResult(null);
    setBlockedReason(null);
    try {
      const result = await launchWorkflow(pid, sid, workflowName, { mode, depth });
      const msg = result.run_id
        ? t("workflow:launch.started").replace("{id}", result.run_id)
        : t("workflow:launch.started_no_id");
      toast(msg, "success");
      setLaunchResult(result.run_id || null);
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

  // No workflow selected → the index (list of Kim-designed workflows).
  if (noSelection) {
    return <WorkflowsList />;
  }

  // A name was given but no such workflow exists → empty state. Nothing else
  // (no graph fixtures, no launcher) until Kim designs one.
  if (workflowsFetched && !workflowExists) {
    return (
      <div
        style={{ height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 40, gap: 14, textAlign: "center" }}
        data-testid="no-workflow-state"
      >
        <div style={{ fontFamily: tokens.ffSerif, fontSize: 22, color: tokens.ink, fontWeight: 500 }}>
          {t("workflow:empty.title")}
        </div>
        <div style={{ fontFamily: tokens.ffSans, fontSize: 14, color: tokens.inkSoft, maxWidth: 360, lineHeight: 1.6 }}>
          {t("workflow:empty.hint")}
        </div>
      </div>
    );
  }

  // Past runs lives in-page (under the title), not in the global sidebar.
  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
        {/* Centre */}
        <aside style={{ flex: 1, display: "flex", flexDirection: "column", gap: 24, padding: `${tokens.tabPadY} ${tokens.tabPadX}`, overflow: "auto" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={heading}>{workflowName}</h3>
            {activeRunId && (
              <InterruptButtonContainer pid={pid} sid={sid} workflowName={workflowName} runId={activeRunId} />
            )}
          </div>

          <section>
            <p style={sectionLabel}>{t("workflow:runs.title")}</p>
            <RunHistoryContainer pid={pid} sid={sid} workflowName={workflowName} />
          </section>

          <WorkflowGraphContainer pid={pid} sid={sid} workflowName={workflowName} runId={activeRunId} />
        </aside>

        {/* Drag handle to resize the right panel */}
        <div
          onMouseDown={panel.onDragStart}
          role="separator"
          aria-orientation="vertical"
          title={t("workflow:panel.resize")}
          style={{
            width: 6, flexShrink: 0, cursor: "col-resize",
            background: panel.dragging ? "color-mix(in srgb, var(--accent) 30%, transparent)" : "transparent",
            borderLeft: `1px solid ${tokens.rule}`,
          }}
        />

        {/* Right panel */}
        <div style={{ width: panel.width, flexShrink: 0, height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {activeRunId ? (
            <WorkflowRunPanel pid={pid} sid={sid} workflowName={workflowName} runId={activeRunId} />
          ) : (
            <div style={{ flex: 1, overflow: "auto" }}>
              <DepthPicker
                workflowName={workflowName}
                onLaunch={handleLaunch}
                t={t}
                estimates={{
                  ...(estimateQuick ? { quick: estimateQuick } : {}),
                  ...(estimateDeep ? { deep: estimateDeep } : {}),
                }}
              />
              {launching && (
                <div style={{ marginTop: 20, textAlign: "center", fontFamily: tokens.ffMono, fontSize: 13, color: tokens.accent }} data-testid="launch-status">
                  {t("workflow:launch.in_progress")}
                </div>
              )}
              {!launching && launchResult && !blockedReason && (
                <div style={{ marginTop: 20, textAlign: "center", fontFamily: tokens.ffMono, fontSize: 13, color: tokens.accent }} data-testid="launch-status">
                  {t("workflow:launch.started").replace("{id}", launchResult)}
                </div>
              )}
              {!launching && blockedReason && (
                <div
                  style={{ marginTop: 20, textAlign: "center", fontFamily: tokens.ffMono, fontSize: 13, color: tokens.danger, lineHeight: 1.5, padding: "0 16px" }}
                  data-testid="launch-blocked"
                >
                  {blockedReason}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
  );
}
