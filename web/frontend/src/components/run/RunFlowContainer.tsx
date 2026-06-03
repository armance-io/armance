"use client";

import { type CSSProperties, type FC } from "react";
import { useTranslation } from "react-i18next";
import { useLiveManifest } from "@/lib/useLiveManifest";
import { displayAgentName } from "@/lib/agentNames";
import { tokens } from "@/components/_shared/armance-tokens";

export interface RunFlowContainerProps {
  pid: string;
  sid: string;
  workflowName: string;
  runId: string;
}

interface ManifestStep {
  id: string;
  status: string;
  role?: string;
  duration_ms?: number;
}

const STATUS_TINT: Record<string, string> = {
  working: "hsl(35, 30%, 60%)",
  completed: "hsl(120, 15%, 55%)",
  failed: "hsl(0, 30%, 65%)",
  queued: "var(--ink-faint, #9c8e7e)",
  skipped: "var(--ink-faint, #9c8e7e)",
  cancelled: "var(--ink-faint, #9c8e7e)",
};

/**
 * Flux tab — the live step-by-step run: which step runs, by which agent, and
 * its status. HITL questions/answers are added here in the next iteration.
 */
export const RunFlowContainer: FC<RunFlowContainerProps> = ({ pid, sid, workflowName, runId }) => {
  const { t } = useTranslation();
  const { data: runFiles } = useLiveManifest(pid, sid, workflowName, runId);

  const manifest = runFiles && runFiles["manifest.json"] ? JSON.parse(runFiles["manifest.json"]) : null;
  const steps: ManifestStep[] = manifest?.steps ?? [];

  const wrap: CSSProperties = { padding: "16px 18px", display: "flex", flexDirection: "column", gap: 10 };
  const row: CSSProperties = {
    display: "flex", alignItems: "center", gap: 10,
    padding: "10px 12px", border: `1px solid ${tokens.rule}`, borderRadius: 4,
    background: tokens.bgPaperCard,
  };

  if (steps.length === 0) {
    return (
      <div style={{ ...wrap, color: tokens.inkSoft, fontStyle: "italic" }}>
        {t("run:flow.waiting")}
      </div>
    );
  }

  return (
    <div style={wrap} data-testid="run-flow">
      {steps.map((s) => {
        const tint = STATUS_TINT[s.status] ?? tokens.inkFaint;
        const working = s.status === "working";
        return (
          <div key={s.id} style={row}>
            <span
              aria-hidden="true"
              style={{
                width: 10, height: 10, borderRadius: 999, flexShrink: 0,
                background: working ? "transparent" : tint,
                border: working ? `2px solid ${tint}` : "none",
                borderTopColor: working ? "transparent" : undefined,
                animation: working ? "runflow-spin 0.8s linear infinite" : "none",
              }}
            />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontFamily: tokens.ffSans, fontSize: 13, color: tokens.ink, fontWeight: 500 }}>{s.id}</div>
              {s.role && (
                <div style={{ fontFamily: tokens.ffSerif, fontStyle: "italic", fontSize: 12, color: tokens.accent }}>
                  {displayAgentName(s.role)}
                </div>
              )}
            </div>
            <span style={{ fontFamily: tokens.ffMono, fontSize: 11, color: tint, textTransform: "uppercase", letterSpacing: "0.06em" }}>
              {t(`run:flow.status.${s.status}`)}
            </span>
            <style>{`@keyframes runflow-spin { to { transform: rotate(360deg); } }`}</style>
          </div>
        );
      })}
    </div>
  );
};

export default RunFlowContainer;
