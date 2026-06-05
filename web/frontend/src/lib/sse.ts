"use client";

import { useEffect, useRef, useState } from "react";

export interface SseEvent {
  name: string;
  data: Record<string, unknown>;
}

// All named SSE event types emitted by the backend.
export const SSE_EVENT_NAMES = [
  "turn.completed",
  "turn.error",
  "agent.streaming.started",
  "agent.streaming",
  "agent.streaming.end",
  // Named event for Malik's recruitment — without this listener the browser
  // never sees it (it arrives with an `event:` field, so `onmessage` skips it)
  // and the sidebar/roster never refreshed after a recruit.
  "agents.proposed",
  "checkpoint.requested",
  "checkpoint.resolved",
  "workflow.step_started",
  "workflow.step_completed",
  "workflow.completed",
] as const;

export function useEventStream(
  pid: string,
  sid: string,
  onEvent?: (evt: SseEvent) => void,
): { connected: boolean; lastEvent: SseEvent | null } {
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<SseEvent | null>(null);

  // Keep the latest callback in a ref so the EventSource is NOT torn down and
  // recreated whenever onEvent's identity changes (e.g. once `agents` loads).
  // A reconnect mid-turn used to drop turn.completed → the input stayed stuck.
  const cbRef = useRef(onEvent);
  cbRef.current = onEvent;

  useEffect(() => {
    if (!sid) return;
    const url = `/api/projects/${pid}/sessions/${sid}/events`;
    const source = new EventSource(url, { withCredentials: true });
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);

    function handleRaw(msg: MessageEvent) {
      try {
        const parsed = JSON.parse(msg.data as string) as Record<string, unknown>;
        const evt: SseEvent = {
          name: String(parsed.name ?? "message"),
          data: parsed,
        };
        setLastEvent(evt);
        cbRef.current?.(evt);
      } catch {
        /* malformed payload — ignore */
      }
    }

    for (const name of SSE_EVENT_NAMES) {
      source.addEventListener(name, handleRaw);
    }
    source.onmessage = handleRaw;

    return () => {
      for (const name of SSE_EVENT_NAMES) {
        source.removeEventListener(name, handleRaw);
      }
      source.close();
    };
  }, [pid, sid]);

  return { connected, lastEvent };
}
