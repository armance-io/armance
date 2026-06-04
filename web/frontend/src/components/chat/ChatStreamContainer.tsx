"use client";

import { type FC, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { submitTurn, getSession, getMessages } from "@/lib/api";
import { useEventStream, type SseEvent } from "@/lib/sse";
import { assignAgentColour } from "@/lib/agent_colours";
import { displayAgentName } from "@/lib/agentNames";
import { onAgentSwitch, setCurrentAgent as publishCurrentAgent, setBusyAgent } from "@/lib/agentBus";
import { lockSession } from "@/lib/sessionBus";
import { BottomSpinner } from "./BottomSpinner";
import { ChatInput } from "./ChatInput";
import { MessageBubble } from "./MessageBubble";
import { EmptySession } from "@/components/visual/EmptyState/EmptySession";

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
  active?: boolean;
}

interface AgentInfo {
  name: string;
  first_name: string;
  title: string;
}

/* ─── Main container ────────────────────────────────────────────────────────── */

export const ChatStreamContainer: FC<ChatStreamContainerProps> = ({ pid, sid, active = true }) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState<BusyAgent | null>(null);
  const [sending, setSending] = useState(false);
  const [currentAgent, setCurrentAgent] = useState("system-context");
  const counter = useRef(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  // Set when *we* initiate an agent switch (sending `@Name`). The next
  // turn.completed is the backend's switch acknowledgement; onSelectAgent
  // already inserted the local separator, so we drop that one bubble. This
  // replaces a fragile multilingual content match — we know structurally,
  // because we triggered it, that the next reply is the ack.
  const awaitingSwitchAck = useRef(false);

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

  // Auto-scroll to bottom on new messages AND when the thinking spinner
  // appears/disappears — the spinner sits below the scroll area and shrinks
  // it, which would otherwise clip the bottom of the just-sent message.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
      // Scroll again after transition completes to prevent overlap/clipping
      const t = setTimeout(() => {
        el.scrollTop = el.scrollHeight;
      }, 210);
      return () => clearTimeout(t);
    }
  }, [messages, busy]);

  const handleEvent = useCallback((evt: SseEvent) => {
    const attrs = (evt.data["attributes"] as Record<string, unknown> | undefined) ?? {};

    // Refresh the roster when Malik recruits new specialists
    if (evt.name === "agents.proposed") {
      void queryClient.invalidateQueries({ queryKey: ["session", pid, sid] });
      return;
    }

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

      // Invalidate session query if the agent is unknown (e.g. newly recruited)
      const known = agents.some((a) => a.first_name === agent || a.name === agent);
      if (!known && agent !== "system") {
        void queryClient.invalidateQueries({ queryKey: ["session", pid, sid] });
      }

      setCurrentAgent((_prev) => {
        const agentInfo = agents.find(
          (a) => a.first_name === agent || a.name === agent,
        );
        // Fall back to agent name (e.g. specialist name) if not found in stale agents roster
        const next = agentInfo?.name ?? agent;
        publishCurrentAgent(next);
        return next;
      });
      // Suppress the switch acknowledgement: onSelectAgent already inserted
      // the separator locally, so the backend's ack reply would only create a
      // duplicate bubble. We know this turn.completed is the ack because we
      // armed the flag when we sent `@Name`.
      const isSwitchAck = awaitingSwitchAck.current;
      awaitingSwitchAck.current = false;
      if (!isSwitchAck) {
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
      }
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
  }, [nextId, t, agents, queryClient, pid, sid]);

  useEventStream(pid, sid, handleEvent);

  // Safety net: unlock the input after 60 s even if no SSE event arrives
  // (network drop, backend crash, EventSource reconnect losing the in-flight
  // turn.completed, etc.).
  const sendingTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startSending = useCallback(() => {
    setSending(true);
    if (sendingTimer.current) clearTimeout(sendingTimer.current);
    sendingTimer.current = setTimeout(() => setSending(false), 60_000);
  }, []);
  // Clear the safety timer whenever sending is explicitly unlocked.
  useEffect(() => {
    if (!sending && sendingTimer.current) {
      clearTimeout(sendingTimer.current);
      sendingTimer.current = null;
    }
  }, [sending]);

  // TUI parity: switching agent never refreshes the conversation — the history
  // stays, only the active agent changes (+ a switch acknowledgement).
  const onSelectAgent = useCallback(
    async (firstName: string) => {
      // Lock the input AND arm the safety timer so the switch turn can't leave
      // the input stuck forever if its turn.completed never reaches the client.
      startSending();
      awaitingSwitchAck.current = true;
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
      try {
        // The switch is lightweight (no streamed reply). The separator is
        // already shown locally, so unlock the input as soon as the POST
        // returns instead of waiting for the turn.completed SSE ack — a
        // switch to the already-current agent produces no ack, which left the
        // input frozen "every other click".
        await submitTurn(pid, sid, `@${firstName}`);
      } catch (err) {
        console.error("Failed to switch agent:", err);
      } finally {
        setSending(false);
      }
    },
    [pid, sid, agents, nextId, t, startSending],
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
      startSending();
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
    [pid, sid, nextId, t, startSending],
  );

  const bottom = useMemo(
    () => (busy === null ? null : { name: busy.name, colour: busy.colour }),
    [busy],
  );

  if (!active) return null;

  return (
    <section style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      {/* R4: no "Talking to" banner — agent selection lives in the sidebar. */}
      {/* paddingLeft only on the scroll area — ChatInput stays flush with the sidebar border. */}
      <div ref={scrollRef} style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "16px 0", paddingLeft: 8 }}>
        {messages.length === 0 ? (
          <EmptySession t={t} />
        ) : (
          <>
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
            {/* Spacer to prevent overlap/clipping by the BottomSpinner */}
            <div style={{ height: busy ? "36px" : "0px", transition: "height 200ms ease" }} />
          </>
        )}
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
