"use client";

/**
 * ChatStreamContainer — wires the visual chat surface to the backend.
 *
 * Subscribes to the SSE event stream for the session, appends the
 * user's message optimistically on submit, then renders `turn.completed`
 * assistant replies. Per-agent streaming flag drives the spinner in
 * MessageBubble + BottomSpinner.
 *
 * Spec: web-c-deliberation.md § C.1 + C.2 + C.8
 *       web-v2-wire-prompts.md  § C-WIRE.1
 */

import { type FC, useCallback, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { submitTurn } from "@/lib/api";
import { useEventStream, type SseEvent } from "@/lib/sse";
import { assignAgentColour, isStaff } from "@/lib/agent_colours";
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
}

interface BusyAgent {
  name: string;
  colour: string;
}

export interface ChatStreamContainerProps {
  pid: string;
  sid: string;
}

export const ChatStreamContainer: FC<ChatStreamContainerProps> = ({ pid, sid }) => {
  const { t } = useTranslation();
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState<BusyAgent | null>(null);
  const [sending, setSending] = useState(false);
  const counter = useRef(0);

  const nextId = useCallback((): string => {
    counter.current += 1;
    return String(counter.current);
  }, []);

  const handleEvent = useCallback((evt: SseEvent) => {
    const attrs = (evt.data["attributes"] as Record<string, unknown> | undefined) ?? {};
    if (evt.name === "turn.completed") {
      const reply = String(attrs["reply"] ?? "");
      const agent = String(attrs["agent"] ?? "Armance");
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
      setBusy(null);
      setSending(false);
    }
  }, [nextId]);

  useEventStream(pid, sid, handleEvent);

  const onSubmit = useCallback(
    async (text: string) => {
      const localId = nextId();
      setMessages((prev) => [
        ...prev,
        {
          id: localId,
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
      }
    },
    [pid, sid, nextId],
  );

  const bottom = useMemo(
    () => (busy === null ? null : { name: busy.name, colour: busy.colour }),
    [busy],
  );

  return (
    <section style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ flex: 1, overflowY: "auto", padding: "16px 0" }}>
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

/* eslint-disable @typescript-eslint/no-unused-vars */
// Silence isStaff unused — kept exported for the AgentTooltip integration
// that lands with C-WIRE.5.
const _STAFF = isStaff;
