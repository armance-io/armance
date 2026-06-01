"use client";

import { type FC, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";

import { submitTurn, getSession, getMessages } from "@/lib/api";
import { useEventStream, type SseEvent } from "@/lib/sse";
import { assignAgentColour } from "@/lib/agent_colours";
import { displayAgentName } from "@/lib/agentNames";
import { onAgentSwitch, setCurrentAgent as publishCurrentAgent, setBusyAgent } from "@/lib/agentBus";
import { lockSession } from "@/lib/sessionBus";
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

  // TUI parity: replay the existing conversation on mount so an existing
  // session shows its history immediately.
  const { data: history } = useQuery({
    queryKey: ["messages", pid, sid],
    queryFn: () => getMessages(pid, sid),
    enabled: Boolean(pid && sid),
  });

  useEffect(() => {
    if (!history) return;
    setMessages(history.map((m) => {
      const agent = m.agent ?? "Armance";
      const isUser = m.role === "user";
      return {
        id: nextId(),
        role: isUser ? "user" as const : "agent" as const,
        agentName: isUser ? "you" : displayAgentName(agent),
        agentColour: isUser ? "var(--ink-soft, #5b5145)" : assignAgentColour(agent),
        markdown: m.content,
        timestamp: m.timestamp ?? new Date().toISOString(),
        streaming: false,
      };
    }));
  }, [history, nextId]);

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

    // Thinking is shown ONLY by the BottomSpinner (outside the input). No
    // placeholder MessageBubble, no in-input busy bar — the full reply lands
    // on turn.completed.
    if (evt.name === "agent.streaming.started") {
      const agent = String(attrs["agent_name"] ?? "Armance");
      const human = displayAgentName(agent);
      setBusy({ name: human, colour: assignAgentColour(human) });
      setBusyAgent(human); // sidebar disc pulse
      return;
    }

    if (evt.name === "agent.streaming") {
      return; // partial chunks ignored; no live placeholder bubble
    }

    if (evt.name === "agent.streaming.end") {
      setBusy(null);
      setBusyAgent(null);
      return;
    }

    if (evt.name === "turn.completed") {
      const reply = String(attrs["reply"] ?? "");
      const agent = String(attrs["agent"] ?? "Armance");
      setCurrentAgent((prev) => {
        const agentInfo = agents.find(
          (a) => a.first_name === agent || a.name === agent,
        );
        const next = agentInfo?.name ?? prev;
        publishCurrentAgent(next);
        return next;
      });
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: "agent" as const,
          agentName: displayAgentName(agent),
          agentColour: assignAgentColour(agent),
          markdown: reply,
          timestamp: new Date().toISOString(),
          streaming: false,
        },
      ]);
      setBusy(null);
      setBusyAgent(null);
      setSending(false);
      return;
    }

    if (evt.name === "turn.error") {
      const err = String(attrs["error"] ?? t("chat:error.turn_failed"));
      setBusy(null);
      setBusyAgent(null);
      setSending(false);
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: "agent" as const,
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

  // Coming from another tab via `?switch=<firstName>` (sidebar agent click):
  // switch to that agent once, then drop the param so refresh is clean.
  const switchedFromUrl = useRef(false);
  useEffect(() => {
    if (switchedFromUrl.current || agents.length === 0) return;
    const params = new URLSearchParams(window.location.search);
    const fn = params.get("switch");
    if (fn) {
      switchedFromUrl.current = true;
      void onSelectAgent(fn);
      const url = new URL(window.location.href);
      url.searchParams.delete("switch");
      window.history.replaceState({}, "", url.toString());
    }
  }, [agents, onSelectAgent]);

  const onSubmit = useCallback(
    async (text: string) => {
      lockSession(); // committing to this session — selector becomes read-only
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
    <section style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      {/* R4: no "Talking to" banner — agent selection lives in the sidebar. */}
      {/* paddingLeft only on the scroll area — ChatInput stays flush with the sidebar border. */}
      <div ref={scrollRef} style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "16px 0", paddingLeft: 8 }}>
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
        onSubmit={(text) => {
          void onSubmit(text);
        }}
        t={t}
      />
    </section>
  );
};

export default ChatStreamContainer;
