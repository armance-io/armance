"use client";

import { useEffect, useState } from "react";

export interface SseEvent {
  name: string;
  data: Record<string, unknown>;
}

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
    source.onmessage = (msg) => {
      try {
        const parsed = JSON.parse(msg.data) as Record<string, unknown>;
        const evt: SseEvent = {
          name: String(parsed.name ?? "message"),
          data: parsed,
        };
        setLastEvent(evt);
        onEvent?.(evt);
      } catch {
        /* malformed payload — ignore */
      }
    };
    return () => source.close();
  }, [pid, sid, onEvent]);

  return { connected, lastEvent };
}
