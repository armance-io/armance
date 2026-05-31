"use client";

import { type CSSProperties, type FC, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";

import { submitTurn, getSession } from "@/lib/api";
import { useEventStream, type SseEvent } from "@/lib/sse";
import { assignAgentColour } from "@/lib/agent_colours";
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

/* ─── Agent picker ──────────────────────────────────────────────────────────── */

interface AgentInfo {
  name: string;
  first_name: string;
  title: string;
}

interface AgentPickerProps {
  agents: AgentInfo[];
  currentAgent: string;
  onSelect: (firstName: string) => void;
  t: (key: string) => string;
}

const AgentPicker: FC<AgentPickerProps> = ({ agents, currentAgent, onSelect, t }) => {
  const rowStyle: CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: 6,
    padding: "6px 16px",
    borderBottom: "1px solid var(--rule-soft, #e8dfcd)",
    overflowX: "auto",
  };

  const chipBase: CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: 5,
    padding: "3px 10px",
    borderRadius: 999,
    border: "1px solid var(--rule, #d6c8ad)",
    fontFamily: "var(--ff-sans, sans-serif)",
    fontSize: 12,
    cursor: "pointer",
    transition: "background 120ms ease, border-color 120ms ease",
    whiteSpace: "nowrap",
    flexShrink: 0,
  };

  const labelStyle: CSSProperties = {
    fontFamily: "var(--ff-mono, monospace)",
    fontSize: 9,
    textTransform: "uppercase",
    letterSpacing: "0.1em",
    color: "var(--ink-faint, #9c8e7e)",
    marginRight: 4,
    userSelect: "none",
  };

  return (
    <div style={rowStyle} aria-label={t("chat:agents.label")}>
      <span style={labelStyle}>{t("chat:agents.label")}</span>
      {agents.map((ag) => {
        const isActive = currentAgent === ag.name || currentAgent === ag.first_name;
        const colour = assignAgentColour(ag.first_name);
        return (
          <button
            key={ag.name}
            type="button"
            style={{
              ...chipBase,
              background: isActive
                ? "color-mix(in srgb, var(--accent, #6b4f8a) 10%, transparent)"
                : "transparent",
              borderColor: isActive ? "var(--accent, #6b4f8a)" : "var(--rule, #d6c8ad)",
              color: isActive ? "var(--accent, #6b4f8a)" : "var(--ink-soft, #5b5145)",
              fontWeight: isActive ? 500 : 400,
            }}
            onClick={() => onSelect(ag.first_name)}
            aria-pressed={isActive}
            aria-label={`${t("chat:agents.switch_aria")} ${ag.first_name}`}
          >
            <span style={{
              width: 7,
              height: 7,
              borderRadius: "999px",
              background: colour,
              flexShrink: 0,
              display: "inline-block",
            }} aria-hidden="true" />
            {ag.first_name}
          </button>
        );
      })}
    </div>
  );
};

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
        return agentInfo?.name ?? prev;
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

  const onSelectAgent = useCallback(
    async (firstName: string) => {
      await submitTurn(pid, sid, `@${firstName}`).catch(() => null);
      const agentInfo = agents.find((a) => a.first_name === firstName);
      if (agentInfo) setCurrentAgent(agentInfo.name);
    },
    [pid, sid, agents],
  );

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
      {agents.length > 0 && (
        <AgentPicker
          agents={agents}
          currentAgent={currentAgent}
          onSelect={(fn) => { void onSelectAgent(fn); }}
          t={t}
        />
      )}
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
