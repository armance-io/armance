"use client";

/**
 * CheckpointDrawerHost — opens the CheckpointDrawer on every
 * `checkpoint.requested` SSE event and resolves it via POST /checkpoint.
 *
 * Backend emits attributes as { checkpoint_id, kind, prompt, options }
 * with `options` JSON-encoded as a string (see backend/checkpoint.py).
 *
 * Spec: web-c-deliberation.md § C.3 + C.4 + C.5
 *       web-v2-wire-prompts.md  § C-WIRE.2
 */

import { type FC, useCallback, useState } from "react";
import { useTranslation } from "react-i18next";

import { resolveCheckpoint } from "@/lib/api";
import { useEventStream, type SseEvent } from "@/lib/sse";
import { CheckpointDrawer } from "./CheckpointDrawer";

interface PendingCheckpoint {
  id: string;
  kind: "text" | "select" | "confirm";
  prompt: string;
  options: string[] | undefined;
}

function parseOptions(raw: unknown): string[] | undefined {
  if (typeof raw !== "string" || raw.length === 0) return undefined;
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.map((s) => String(s)) : undefined;
  } catch {
    return undefined;
  }
}

export interface CheckpointDrawerHostProps {
  pid: string;
  sid: string;
}

export const CheckpointDrawerHost: FC<CheckpointDrawerHostProps> = ({ pid, sid }) => {
  const { t } = useTranslation();
  const [pending, setPending] = useState<PendingCheckpoint | null>(null);

  const handleEvent = useCallback((evt: SseEvent) => {
    if (evt.name !== "checkpoint.requested") return;
    const attrs = (evt.data["attributes"] as Record<string, unknown> | undefined) ?? {};
    const id = String(attrs["checkpoint_id"] ?? "");
    const kindRaw = String(attrs["kind"] ?? "text");
    const kind: PendingCheckpoint["kind"] =
      kindRaw === "select" || kindRaw === "confirm" ? kindRaw : "text";
    if (id === "") return;
    setPending({
      id,
      kind,
      prompt: String(attrs["prompt"] ?? ""),
      options: parseOptions(attrs["options"]),
    });
  }, []);

  useEventStream(pid, sid, handleEvent);

  const close = useCallback(() => setPending(null), []);

  const onSubmit = useCallback(
    async (content: string) => {
      if (pending === null) return;
      try {
        await resolveCheckpoint(pid, sid, {
          checkpoint_id: pending.id,
          content,
          is_abort: false,
        });
      } finally {
        close();
      }
    },
    [pending, pid, sid, close],
  );

  const onAbort = useCallback(async () => {
    if (pending === null) return;
    try {
      await resolveCheckpoint(pid, sid, {
        checkpoint_id: pending.id,
        content: "",
        is_abort: true,
      });
    } finally {
      close();
    }
  }, [pending, pid, sid, close]);

  if (pending === null) return null;
  return (
    <CheckpointDrawer
      kind={pending.kind}
      prompt={pending.prompt}
      {...(pending.options !== undefined ? { options: pending.options } : {})}
      onSubmit={(content) => {
        void onSubmit(content);
      }}
      onAbort={() => {
        void onAbort();
      }}
      t={t}
    />
  );
};

export default CheckpointDrawerHost;
