"use client";

/**
 * PanelCardsHost — subscribes to `agents.proposed` SSE events and
 * renders Malik's recruited panel as cards.
 *
 * Approval posts a chat turn back to Malik (so the user's approval is
 * recorded in the conversation). Cancel/ask-alternative focuses the
 * chat input — done by the parent via the `onAskAlternative` prop.
 *
 * Spec: web-c-deliberation.md § C.3 + C.6
 *       web-v2-wire-prompts.md  § C-WIRE.3
 */

import { type FC, useCallback, useState } from "react";
import { useTranslation } from "react-i18next";

import { submitTurn } from "@/lib/api";
import { useEventStream, type SseEvent } from "@/lib/sse";
import { assignAgentColour } from "@/lib/agent_colours";
import { PanelCards } from "./PanelCards";

interface AgentProposed {
  name: string;
  role: string;
  persona: string;
  description: string;
  provider: string;
  model: string;
  reasoning: string | null;
}

interface PanelMemberView {
  name: string;
  role: string;
  persona: string;
  axis: string;
  provider: string;
  model: string;
  colour: string;
  reasoning?: "low" | "medium" | "high";
}

function isReasoning(s: unknown): s is "low" | "medium" | "high" {
  return s === "low" || s === "medium" || s === "high";
}

function toView(a: AgentProposed): PanelMemberView {
  const base: PanelMemberView = {
    name: a.name,
    role: a.role,
    persona: a.persona,
    // The backend payload doesn't carry an `axis` yet — surface the
    // persona label as the axis chip until Malik emits it explicitly.
    axis: a.persona || a.role,
    provider: a.provider,
    model: a.model,
    colour: assignAgentColour(a.name),
  };
  if (isReasoning(a.reasoning)) base.reasoning = a.reasoning;
  return base;
}

export interface PanelCardsHostProps {
  pid: string;
  sid: string;
  onAskAlternative?: () => void;
}

export const PanelCardsHost: FC<PanelCardsHostProps> = ({ pid, sid, onAskAlternative }) => {
  const { t } = useTranslation();
  const [panel, setPanel] = useState<PanelMemberView[]>([]);

  const handleEvent = useCallback((evt: SseEvent) => {
    if (evt.name !== "agents.proposed") return;
    const attrs = (evt.data["attributes"] as Record<string, unknown> | undefined) ?? {};
    const agents = attrs["agents"];
    if (!Array.isArray(agents)) return;
    setPanel(agents.map((a) => toView(a as AgentProposed)));
  }, []);

  useEventStream(pid, sid, handleEvent);

  const onApprove = useCallback(async () => {
    setPanel([]);
    try {
      await submitTurn(pid, sid, t("panel:approve"));
    } catch {
      /* swallow — the chat shows the error path */
    }
  }, [pid, sid, t]);

  if (panel.length === 0) return null;

  return (
    <PanelCards
      panel={panel}
      onApprove={() => {
        void onApprove();
      }}
      onAskAlternative={() => {
        setPanel([]);
        onAskAlternative?.();
      }}
      t={t}
    />
  );
};

export default PanelCardsHost;
