"use client";

import { type FC, useEffect } from "react";
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
  const model = agent?.effective_model ?? agent?.model;
  const isBoosted = agent?.boosted ?? false;

  useEffect(() => {
    const headerEl = document.querySelector("header");
    if (!headerEl) return;
    if (isBoosted) {
      headerEl.classList.add("ae-header-boost-glow");
    } else {
      headerEl.classList.remove("ae-header-boost-glow");
    }
    return () => {
      headerEl.classList.remove("ae-header-boost-glow");
    };
  }, [isBoosted]);

  if (!model) return null;

  return (
    <>
      <style>{`
        @keyframes ae-header-boost-glow {
          0% {
            box-shadow: 0 0 4px rgba(107, 79, 138, 0.15), inset 0 0 10px rgba(107, 79, 138, 0.1);
            background-color: var(--bg, #f5f2eb);
          }
          100% {
            box-shadow: 0 0 12px rgba(107, 79, 138, 0.45), inset 0 0 20px rgba(107, 79, 138, 0.2);
            background-color: color-mix(in srgb, var(--accent) 15%, var(--bg, #f5f2eb));
          }
        }
        .ae-header-boost-glow {
          animation: ae-header-boost-glow 1.5s infinite alternate !important;
          transition: background-color 0.5s ease, box-shadow 0.5s ease;
        }
      `}</style>
      <span
        data-testid="header-model"
        title={t("visual:metrics.model_aria")}
        style={{
          display: "inline-flex", alignItems: "center", gap: 5,
          fontFamily: tokens.ffMono, fontSize: 11, color: tokens.inkSoft,
          whiteSpace: "nowrap", maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis",
        }}
      >
        <span aria-hidden="true" style={{ color: isBoosted ? "var(--accent)" : tokens.inkSoft }}>◆</span>
        <span style={{ color: isBoosted ? "var(--accent-deep, var(--accent))" : tokens.ink, fontWeight: isBoosted ? 600 : 400 }}>
          {model}
        </span>
      </span>
    </>
  );
};

export default HeaderModel;
