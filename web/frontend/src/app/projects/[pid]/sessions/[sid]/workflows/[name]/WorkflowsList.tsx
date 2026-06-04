"use client";

import { type CSSProperties, type FC } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";

import { listWorkflows } from "@/lib/api";
import { useRouteParams } from "@/lib/routeParams";
import { emitViewChange } from "@/lib/navigationBus";
import { tokens } from "@/components/_shared/armance-tokens";

/**
 * Workflows index — the list of workflows the user has designed with Kim.
 *
 * Shown when no specific workflow is selected (`/workflows/_`). Clicking a row
 * soft-navigates to that workflow's detail (graph + run history + launch),
 * staying inside the SPA shell — no reload. A workflow only appears here once
 * Kim has designed it; there is no built-in/default workflow.
 */
export const WorkflowsList: FC = () => {
  const { pid, sid } = useRouteParams();
  const { t } = useTranslation();

  const { data, isFetched } = useQuery({
    queryKey: ["workflows", pid, sid],
    queryFn: () => listWorkflows(pid, sid).catch(() => ({ workflows: [] })),
    enabled: Boolean(pid && sid),
  });
  const workflows = data?.workflows ?? [];

  const openWorkflow = (name: string) => {
    window.history.pushState(null, "", `/projects/${pid}/sessions/${sid}/workflows/${encodeURIComponent(name)}`);
    emitViewChange("workflows");
  };

  const heading: CSSProperties = {
    fontFamily: tokens.ffSerif, fontSize: 24, color: tokens.ink, margin: 0, fontWeight: 500,
  };
  const card: CSSProperties = {
    display: "flex", flexDirection: "column", gap: 6, width: "100%", textAlign: "left",
    padding: "16px 18px", background: tokens.bgPaperCard, border: `1px solid ${tokens.rule}`,
    borderRadius: tokens.radiusSm, cursor: "pointer", transition: "border-color 120ms ease",
  };
  const name: CSSProperties = {
    fontFamily: tokens.ffSerif, fontSize: 18, color: tokens.ink, fontWeight: 500,
  };
  const scope: CSSProperties = {
    fontFamily: tokens.ffSans, fontSize: 13, color: tokens.inkSoft, lineHeight: 1.5,
  };
  const meta: CSSProperties = {
    fontFamily: tokens.ffMono, fontSize: 11, color: tokens.inkFaint, letterSpacing: "0.04em",
  };

  // No workflow designed yet → designed empty state.
  if (isFetched && workflows.length === 0) {
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

  return (
    <div
      style={{ display: "flex", flexDirection: "column", gap: 20, padding: `${tokens.tabPadY} ${tokens.tabPadX}`, overflow: "auto", height: "100%" }}
      data-testid="workflows-list"
    >
      <h3 style={heading}>{t("workflow:list.title")}</h3>
      <div style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 720 }}>
        {workflows.map((w) => (
          <button
            key={w.name}
            type="button"
            style={card}
            onClick={() => openWorkflow(w.name)}
            data-testid={`workflow-row-${w.name}`}
          >
            <span style={name}>{w.name}</span>
            {w.scope && <span style={scope}>{w.scope}</span>}
            <span style={meta}>
              {t("workflow:list.steps").replace("{count}", String(w.step_count))}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
};

export default WorkflowsList;
