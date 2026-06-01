"use client";

import { type FC } from "react";
import { useQuery } from "@tanstack/react-query";
import { getAdminAgents } from "@/lib/api";
import { useCurrentAgent } from "@/lib/agentBus";
import { useRouteParams } from "@/lib/routeParams";
import { tokens } from "../_shared/armance-tokens";

/**
 * Header chip: the model in use for the currently selected agent. Reads the
 * active agent from the agentBus and looks up its (effective) model from the
 * agents list — so it follows agent switches.
 */
export const HeaderModel: FC<{ t: (k: string) => string }> = ({ t }) => {
  const { pid, sid } = useRouteParams();
  const current = useCurrentAgent();

  const { data: agents = [] } = useQuery({
    queryKey: ["header-agents", pid, sid],
    enabled: Boolean(pid && sid && sid !== "_"),
    queryFn: () => getAdminAgents(pid, sid).catch(() => []),
  });

  const agent = agents.find((a) => a.slug === current || a.name === current);
  const model = agent?.model;
  if (!model) return null;

  return (
    <span
      title={t("visual:metrics.model_aria")}
      style={{
        display: "inline-flex", alignItems: "center", gap: 5,
        fontFamily: tokens.ffMono, fontSize: 11, color: tokens.inkSoft,
        whiteSpace: "nowrap", maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis",
      }}
    >
      <span aria-hidden="true">◆</span>
      <span style={{ color: tokens.ink }}>{model}</span>
    </span>
  );
};

export default HeaderModel;
