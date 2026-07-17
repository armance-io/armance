"use client";

import { type FC, useState, useMemo, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useRouter } from "next/navigation";
import { loadRun, loadRunDetail, loadStep, type RunDetailResponse } from "@/lib/api";
import { RunDetail, type Run } from "./RunDetail";

export interface RunDetailContainerProps {
  pid: string;
  sid: string;
  workflowName: string;
  runId: string;
}

interface StepManifest {
  id: string;
  status: string;
  started_at?: string;
  ended_at?: string;
  duration_ms?: number;
  tokens_in?: number;
  tokens_out?: number;
  cost_usd?: number;
  output_path?: string;
  error?: string;
}

interface RunManifest {
  run_id: string;
  workflow: string;
  started_at: string;
  ended_at?: string;
  duration_ms?: number;
  status: string;
  steps?: StepManifest[];
  totals?: {
    tokens_in?: number;
    tokens_out?: number;
    cost_usd?: number;
  };
}

function msBetween(start: string | null, end: string | null): number | null {
  if (!start || !end) return null;
  const ms = new Date(end).getTime() - new Date(start).getTime();
  return Number.isFinite(ms) && ms >= 0 ? ms : null;
}

/** Sum a per-step numeric field; null when NO step carries it (never invent). */
function sumOrNull(
  steps: RunDetailResponse["steps"],
  key: "tokens_in" | "tokens_out" | "cost_usd",
): number | null {
  const vals = steps
    .map((s) => s[key])
    .filter((v): v is number => v !== null && v !== undefined);
  if (vals.length === 0) return null;
  return vals.reduce((a, b) => a + b, 0);
}

/** Structured `/detail` payload → view model. */
function fromDetail(detail: RunDetailResponse): Run {
  return {
    run_id: detail.run_id,
    workflow: detail.workflow,
    started_at: detail.started_at ?? "",
    ended_at: detail.ended_at,
    duration_ms: msBetween(detail.started_at, detail.ended_at),
    status: detail.status,
    tokens_in: sumOrNull(detail.steps, "tokens_in"),
    tokens_out: sumOrNull(detail.steps, "tokens_out"),
    cost_usd: sumOrNull(detail.steps, "cost_usd"),
    quality: detail.quality,
    derived_from: detail.derived_from,
    steps: detail.steps.map((s) => ({
      id: s.id,
      role: s.id,
      status: s.status,
      started_at: "",
      ended_at: null,
      duration_ms: s.duration_ms ?? null,
      tokens_in: s.tokens_in ?? null,
      tokens_out: s.tokens_out ?? null,
      cost_usd: s.cost_usd ?? null,
      stage: s.stage ?? null,
      family: s.family ?? null,
      agent: s.agent ?? null,
      provided: s.provided,
      error: s.error ?? null,
      output: "", // loaded lazily
    })),
  };
}

/** Legacy raw `manifest.json` → view model (older backends, 404 fallback). */
function fromManifest(manifest: RunManifest): Run {
  return {
    run_id: manifest.run_id,
    workflow: manifest.workflow,
    started_at: manifest.started_at,
    ended_at: manifest.ended_at || null,
    duration_ms: manifest.duration_ms ?? null,
    status: manifest.status,
    tokens_in: manifest.totals?.tokens_in ?? null,
    tokens_out: manifest.totals?.tokens_out ?? null,
    cost_usd: manifest.totals?.cost_usd ?? null,
    steps: (manifest.steps || []).map((step) => ({
      id: step.id,
      role: step.id, // default role to step.id
      status: step.status,
      started_at: step.started_at || "",
      ended_at: step.ended_at || null,
      duration_ms: step.duration_ms ?? null,
      tokens_in: step.tokens_in ?? null,
      tokens_out: step.tokens_out ?? null,
      output: "", // loaded lazily
    })),
  };
}

export const RunDetailContainer: FC<RunDetailContainerProps> = ({
  pid,
  sid,
  workflowName,
  runId,
}) => {
  const { t } = useTranslation();
  const router = useRouter();
  // Lazily fetched step outputs, keyed by step id.
  const [outputs, setOutputs] = useState<Record<string, string>>({});

  // Structured Creuset-aware detail first; `null` means the backend lacks
  // the /detail route (404) and we fall back to the raw manifest below.
  // `isPending` (not `isLoading`) — on the very first render the fetch has
  // not started yet, so isLoading is briefly false and the legacy fallback
  // below would fire a wasted request alongside the structured one.
  const { data: detail, isPending: detailPending } = useQuery({
    queryKey: ["run-detail", pid, sid, workflowName, runId],
    queryFn: () => loadRunDetail(pid, sid, workflowName, runId).catch(() => null),
  });

  const needFallback = !detailPending && !detail;
  const { data, isLoading: legacyLoading, isError } = useQuery({
    queryKey: ["run", pid, sid, workflowName, runId],
    queryFn: () => loadRun(pid, sid, workflowName, runId),
    enabled: needFallback,
  });

  const baseRun = useMemo<Run | null>(() => {
    if (detail) return fromDetail(detail);
    if (data && data["manifest.json"]) {
      try {
        return fromManifest(JSON.parse(data["manifest.json"]) as RunManifest);
      } catch (e) {
        console.error("Failed to parse run manifest", e);
      }
    }
    return null;
  }, [detail, data]);

  const run = useMemo<Run | null>(() => {
    if (!baseRun) return null;
    return {
      ...baseRun,
      steps: baseRun.steps.map((s) =>
        outputs[s.id] ? { ...s, output: outputs[s.id] as string } : s,
      ),
    };
  }, [baseRun, outputs]);

  const onStepExpand = async (stepId: string) => {
    if (outputs[stepId]) return;
    try {
      const markdown = await loadStep(pid, sid, workflowName, runId, stepId);
      setOutputs((prev) => ({ ...prev, [stepId]: markdown }));
    } catch (e) {
      console.error("Failed to load step markdown", e);
    }
  };

  const onOpenRun = useCallback(
    (parentRunId: string) => {
      router.push(
        `/projects/${pid}/sessions/${sid}/workflows/${encodeURIComponent(workflowName)}/runs/${encodeURIComponent(parentRunId)}`,
      );
    },
    [router, pid, sid, workflowName],
  );

  if (detailPending || (needFallback && legacyLoading)) {
    return (
      <div style={{ padding: "20px", color: "var(--ink-soft)" }}>
        {t("app:loading")}
      </div>
    );
  }

  if (isError || !run) {
    return (
      <div style={{ padding: "20px", color: "hsl(0, 30%, 45%)" }}>
        {t("common:error")}
      </div>
    );
  }

  return (
    <RunDetail run={run} onStepExpand={onStepExpand} onOpenRun={onOpenRun} t={t} />
  );
};

export default RunDetailContainer;
