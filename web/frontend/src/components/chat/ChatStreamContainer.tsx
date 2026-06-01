"use client";

import { type FC, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";

import { submitTurn, getSession } from "@/lib/api";
import { useEventStream, type SseEvent } from "@/lib/sse";
import { assignAgentColour } from "@/lib/agent_colours";
import { onAgentSwitch, setCurrentAgent as publishCurrentAgent } from "@/lib/agentBus";
import { BottomSpinner } from "./BottomSpinner";
import { ChatInput } from "./ChatInput";
import { MessageBubble } from "./MessageBubble";

interface Message {
  id: string;
  role: "user" | "agent";
  agentName: string;
  agentColour: string;
  markdown: string;
  timestamp: string;
  streaming: boolean;
  isError?: boolean;
}

interface BusyAgent {
  name: string;
  colour: string;
}

export interface ChatStreamContainerProps {
  pid: string;
  sid: string;
}

interface AgentInfo {
  name: string;
  first_name: string;
  title: string;
}

/* ─── Main container ────────────────────────────────────────────────────────── */

export const ChatStreamContainer: FC<ChatStreamContainerProps> = ({ pid, sid }) => {
  const { t } = useTranslation();
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState<BusyAgent | null>(null);
  const [sending, setSending] = useState(false);
  const [currentAgent, setCurrentAgent] = useState("system-context");
  const counter = useRef(0);
  const scrollRef = useRef<HTMLDivElement>(null);

  const nextId = useCallback((): string => {
    counter.current += 1;
    return String(counter.current);
  }, []);

  const { data: sessionData } = useQuery({
    queryKey: ["session", pid, sid],
    queryFn: () => getSession(pid, sid),
    enabled: Boolean(pid && sid),
  });

  const agents: AgentInfo[] = useMemo(() => sessionData?.agents ?? [], [sessionData]);

  useEffect(() => {
    if (sessionData?.state) {
      const ca = (sessionData.state as Record<string, unknown>)["current_agent"];
      if (typeof ca === "string" && ca) setCurrentAgent(ca);
    }
  }, [sessionData]);

  // Mirror the active agent to the sidebar bus so the L2 row highlights.
  useEffect(() => { publishCurrentAgent(currentAgent); }, [currentAgent]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const handleEvent = useCallback((evt: SseEvent) => {
    const attrs = (evt.data["attributes"] as Record<string, unknown> | undefined) ?? {};
    if (evt.name === "turn.completed") {
      const reply = String(attrs["reply"] ?? "");
      const agent = String(attrs["agent"] ?? "Armance");
      setCurrentAgent((prev) => {
        const agentInfo = agents.find(
          (a) => a.first_name === agent || a.name === agent,
        );
        const next = agentInfo?.name ?? prev;
        publishCurrentAgent(next); // keep the sidebar L2 selection in sync
        return next;
      });
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: "agent",
          agentName: agent,
          agentColour: assignAgentColour(agent),
          markdown: reply,
          timestamp: new Date().toISOString(),
          streaming: false,
        },
      ]);
      setBusy(null);
      setSending(false);
      return;
    }
    if (evt.name === "agent_streaming_started") {
      const agent = String(attrs["agent_name"] ?? "Armance");
      setBusy({ name: agent, colour: assignAgentColour(agent) });
      return;
    }
    if (evt.name === "agent_streaming_end") {
      setBusy(null);
      return;
    }
    if (evt.name === "turn.error") {
      const err = String(attrs["error"] ?? t("chat:error.turn_failed"));
      setBusy(null);
      setSending(false);
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: "agent",
          agentName: "system",
          agentColour: "var(--danger, #a44141)",
          markdown: `⚠ ${err}`,
          timestamp: new Date().toISOString(),
          streaming: false,
          isError: true,
        },
      ]);
    }
  }, [nextId, t, agents]);

  useEventStream(pid, sid, handleEvent);

  // TUI parity: switching agent never refreshes the conversation — the history
  // stays, only the active agent changes (+ a "basculé sur X" acknowledgement).
  const onSelectAgent = useCallback(
    async (firstName: string) => {
      const agentInfo = agents.find((a) => a.first_name === firstName);
      const slug = agentInfo?.name ?? firstName;
      setCurrentAgent(slug);
      publishCurrentAgent(slug);
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: "agent",
          agentName: "system",
          agentColour: "var(--ink-faint, #9c8e7e)",
          markdown: t("chat:agents.switched").replace("{name}", firstName),
          timestamp: new Date().toISOString(),
          streaming: false,
        },
      ]);
      await submitTurn(pid, sid, `@${firstName}`).catch(() => null);
    },
    [pid, sid, agents, nextId, t],
  );

  // Sidebar Staff click → switch here (no navigation, history preserved).
  useEffect(() => onAgentSwitch((fn) => { void onSelectAgent(fn); }), [onSelectAgent]);

  const onSubmit = useCallback(
    async (text: string) => {
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: "user",
          agentName: "you",
          agentColour: "var(--ink-soft, #5b5145)",
          markdown: text,
          timestamp: new Date().toISOString(),
          streaming: false,
        },
      ]);
      setSending(true);
      try {
        await submitTurn(pid, sid, text);
      } catch {
        setSending(false);
        setMessages((prev) => [
          ...prev,
          {
            id: nextId(),
            role: "agent",
            agentName: "system",
            agentColour: "var(--danger, #a44141)",
            markdown: `⚠ ${t("chat:error.turn_failed")}`,
            timestamp: new Date().toISOString(),
            streaming: false,
            isError: true,
          },
        ]);
      }
    },
    [pid, sid, nextId, t],
  );

  const bottom = useMemo(
    () => (busy === null ? null : { name: busy.name, colour: busy.colour }),
    [busy],
  );

  return (
    <section style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* R4: no "Talking to" banner — agent selection lives in the sidebar. */}
      <div ref={scrollRef} style={{ flex: 1, overflowY: "auto", padding: "16px 0" }}>
        {messages.map((m) => (
          <MessageBubble
            key={m.id}
            role={m.role}
            agentName={m.agentName}
            agentColour={m.agentColour}
            markdown={m.markdown}
            timestamp={m.timestamp}
            streaming={m.streaming}
            t={t}
          />
        ))}
      </div>
      <BottomSpinner busy={bottom} t={t} />
      <ChatInput
        placeholder={t("chat:input.placeholder")}
        disabled={sending}
        {...(busy !== null
          ? { busyAgentName: busy.name, busyAgentColour: busy.colour }
          : {})}
        onSubmit={(text) => {
          void onSubmit(text);
        }}
        t={t}
      />
    </section>
  );
};

export default ChatStreamContainer;
