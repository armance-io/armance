"use client";

import { useEffect, useState } from "react";

export interface SseEvent {
  name: string;
  data: Record<string, unknown>;
}

// All named SSE event types emitted by the backend.
const SSE_EVENT_NAMES = [
  "turn.completed",
  "turn.error",
  "agent_streaming_started",
  "agent_streaming",
  "agent_streaming_end",
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
        onEvent?.(evt);
      } catch {
        /* malformed payload — ignore */
      }
    }

    // Named events (sse_starlette emits event: <name> field).
    for (const name of SSE_EVENT_NAMES) {
      source.addEventListener(name, handleRaw);
    }
    // Fallback for any unnamed events.
    source.onmessage = handleRaw;

    return () => {
      for (const name of SSE_EVENT_NAMES) {
        source.removeEventListener(name, handleRaw);
      }
      source.close();
    };
  }, [pid, sid, onEvent]);

  return { connected, lastEvent };
}
