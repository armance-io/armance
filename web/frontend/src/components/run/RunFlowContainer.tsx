"use client";

import { type CSSProperties, type FC, useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLiveManifest } from "@/lib/useLiveManifest";
import { useEventStream, type SseEvent } from "@/lib/sse";
import { resolveCheckpoint } from "@/lib/api";
import { displayAgentName } from "@/lib/agentNames";
import { useToast } from "@/components/_shared/Toast";
import { tokens } from "@/components/_shared/armance-tokens";

export interface RunFlowContainerProps {
  pid: string;
  sid: string;
  workflowName: string;
  runId: string;
}

interface ManifestStep {
  id: string;
  status: string;
  role?: string;
}

interface PendingCheckpoint {
  id: string;
  kind: "text" | "select" | "confirm";
  prompt: string;
  options?: string[];
}

const STATUS_TINT: Record<string, string> = {
  working: "hsl(35, 30%, 60%)",
  completed: "hsl(120, 15%, 55%)",
  failed: "hsl(0, 30%, 65%)",
  queued: "var(--ink-faint, #9c8e7e)",
  skipped: "var(--ink-faint, #9c8e7e)",
  cancelled: "var(--ink-faint, #9c8e7e)",
};

function parseOptions(raw: unknown): string[] | undefined {
  if (typeof raw !== "string" || !raw) return undefined;
  try {
    const v = JSON.parse(raw);
    return Array.isArray(v) ? v.map(String) : undefined;
  } catch {
    return undefined;
  }
}

/**
 * Flux tab — the live step-by-step run: which step runs, by which agent, its
 * status, and any HITL question the run is waiting on (answered inline). The
 * workflow is a dedicated space, distinct from the conversation.
 */
export const RunFlowContainer: FC<RunFlowContainerProps> = ({ pid, sid, workflowName, runId }) => {
  const { t } = useTranslation();
  const { toast } = useToast();
  const { data: runFiles } = useLiveManifest(pid, sid, workflowName, runId);
  const [pending, setPending] = useState<PendingCheckpoint | null>(null);
  const [answer, setAnswer] = useState("");
  const [resolving, setResolving] = useState(false);

  const onSse = useCallback((evt: SseEvent) => {
    if (evt.name !== "checkpoint.requested") return;
    const attrs = (evt.data["attributes"] as Record<string, unknown> | undefined) ?? {};
    const kindRaw = String(attrs["kind"] ?? "text");
    const kind = kindRaw === "select" || kindRaw === "confirm" ? kindRaw : "text";
    const opts = parseOptions(attrs["options"]);
    setPending({
      id: String(attrs["checkpoint_id"] ?? ""),
      kind,
      prompt: String(attrs["prompt"] ?? ""),
      ...(opts !== undefined ? { options: opts } : {}),
    });
    setAnswer("");
    // Bottom-right notif so the user notices the run is waiting on them.
    toast(t("run:flow.question_notif"), "info");
  }, [toast, t]);
  useEventStream(pid, sid, onSse);

  const resolve = async (content: string, isAbort = false) => {
    if (!pending) return;
    setResolving(true);
    try {
      await resolveCheckpoint(pid, sid, { checkpoint_id: pending.id, content, is_abort: isAbort });
      setPending(null);
      setAnswer("");
    } finally {
      setResolving(false);
    }
  };

  const manifest = runFiles && runFiles["manifest.json"] ? JSON.parse(runFiles["manifest.json"]) : null;
  const steps: ManifestStep[] = manifest?.steps ?? [];

  const wrap: CSSProperties = { padding: "16px 18px", display: "flex", flexDirection: "column", gap: 10 };
  const row: CSSProperties = {
    display: "flex", alignItems: "center", gap: 10,
    padding: "10px 12px", border: `1px solid ${tokens.rule}`, borderRadius: 4,
    background: tokens.bgPaperCard,
  };
  const input: CSSProperties = {
    flex: 1, padding: "8px 10px", border: `1px solid ${tokens.rule}`, borderRadius: 4,
    background: tokens.bgPaper, color: tokens.ink, fontFamily: tokens.ffSans, fontSize: 13, outline: "none",
  };
  const btn = (primary?: boolean): CSSProperties => ({
    padding: "8px 14px", borderRadius: 999,
    border: `1px solid ${primary ? tokens.accent : tokens.rule}`,
    background: primary ? tokens.accent : "transparent",
    color: primary ? tokens.bgPaperCard : tokens.inkSoft,
    fontFamily: tokens.ffSans, fontSize: 13, cursor: "pointer", flexShrink: 0,
  });

  return (
    <div style={wrap} data-testid="run-flow">
      {pending && (
        <div
          data-testid="run-flow-hitl"
          style={{
            border: `1px solid ${tokens.accent}`, borderRadius: 4, padding: "12px 14px",
            background: "color-mix(in srgb, var(--accent) 7%, transparent)",
            display: "flex", flexDirection: "column", gap: 10,
          }}
        >
          <div style={{ fontFamily: tokens.ffSans, fontSize: 13, color: tokens.ink, fontWeight: 500 }}>
            {pending.prompt}
          </div>
          {pending.kind === "confirm" ? (
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button type="button" disabled={resolving} style={btn()} onClick={() => resolve("no")}>
                {t("checkpoint:drawer.no")}
              </button>
              <button type="button" disabled={resolving} style={btn(true)} onClick={() => resolve("yes")}>
                {t("checkpoint:drawer.yes")}
              </button>
            </div>
          ) : pending.kind === "select" && pending.options ? (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {pending.options.map((opt) => (
                <button key={opt} type="button" disabled={resolving} style={btn()} onClick={() => resolve(opt)}>
                  {opt}
                </button>
              ))}
            </div>
          ) : (
            <div style={{ display: "flex", gap: 8 }}>
              <input
                style={input}
                value={answer}
                autoFocus
                placeholder={t("run:flow.answer_placeholder")}
                onChange={(e) => setAnswer(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && answer.trim()) void resolve(answer.trim()); }}
              />
              <button type="button" disabled={resolving || !answer.trim()} style={btn(true)} onClick={() => resolve(answer.trim())}>
                {t("run:flow.answer_send")}
              </button>
            </div>
          )}
        </div>
      )}

      {steps.length === 0 && !pending ? (
        <div style={{ color: tokens.inkSoft, fontStyle: "italic" }}>{t("run:flow.waiting")}</div>
      ) : (
        steps.map((s) => {
          const tint = STATUS_TINT[s.status] ?? tokens.inkFaint;
          const working = s.status === "working";
          const awaiting = working && pending != null;
          return (
            <div key={s.id} style={row}>
              {awaiting ? (
                <span
                  aria-hidden="true"
                  title={t("run:flow.awaiting_answer")}
                  style={{
                    width: 14, height: 14, borderRadius: 999, flexShrink: 0,
                    display: "grid", placeItems: "center",
                    color: tokens.accent, fontWeight: 700, fontSize: 11,
                    animation: "runflow-qpulse 1s ease-in-out infinite",
                  }}
                >?</span>
              ) : (
                <span
                  aria-hidden="true"
                  style={{
                    width: 10, height: 10, borderRadius: 999, flexShrink: 0,
                    background: working ? "transparent" : tint,
                    border: working ? `2px solid ${tint}` : "none",
                    animation: working ? "runflow-spin 0.8s linear infinite" : "none",
                  }}
                />
              )}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontFamily: tokens.ffSans, fontSize: 13, color: tokens.ink, fontWeight: 500 }}>{s.id}</div>
                {s.role && (
                  <div style={{ fontFamily: tokens.ffSerif, fontStyle: "italic", fontSize: 12, color: tokens.accent }}>
                    {displayAgentName(s.role)}
                  </div>
                )}
              </div>
              <span style={{ fontFamily: tokens.ffMono, fontSize: 11, color: tint, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                {t(awaiting ? "run:flow.status.awaiting" : `run:flow.status.${s.status}`)}
              </span>
            </div>
          );
        })
      )}
      <style>{`
        @keyframes runflow-spin { to { transform: rotate(360deg); } }
        @keyframes runflow-qpulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
      `}</style>
    </div>
  );
};

export default RunFlowContainer;
