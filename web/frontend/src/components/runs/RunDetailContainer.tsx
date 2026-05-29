"use client";

import { type FC, useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { loadRun, loadStep } from "@/lib/api";
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

type RunStatus = "running" | "completed" | "failed" | "cancelled";

function mapStatus(status: string): RunStatus {
  if (status === "running" || status === "completed" || status === "failed" || status === "cancelled") {
    return status;
  }
  return "running";
}

export const RunDetailContainer: FC<RunDetailContainerProps> = ({
  pid,
  sid,
  workflowName,
  runId,
}) => {
  const { t } = useTranslation();
  const [run, setRun] = useState<Run | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["run", pid, sid, workflowName, runId],
    queryFn: () => loadRun(pid, sid, workflowName, runId),
  });

  useEffect(() => {
    if (data && data["manifest.json"]) {
      try {
        const manifest = JSON.parse(data["manifest.json"]) as RunManifest;
        const steps = (manifest.steps || []).map((step) => ({
          id: step.id,
          role: step.id, // default role to step.id
          status: mapStatus(step.status),
          started_at: step.started_at || "",
          ended_at: step.ended_at || null,
          duration_ms: step.duration_ms ?? null,
          tokens_in: step.tokens_in ?? null,
          tokens_out: step.tokens_out ?? null,
          output: "", // loaded lazily
        }));

        setRun({
          run_id: manifest.run_id,
          workflow: manifest.workflow,
          started_at: manifest.started_at,
          ended_at: manifest.ended_at || null,
          duration_ms: manifest.duration_ms ?? null,
          status: mapStatus(manifest.status),
          tokens_in: manifest.totals?.tokens_in ?? null,
          tokens_out: manifest.totals?.tokens_out ?? null,
          cost_usd: manifest.totals?.cost_usd ?? null,
          steps,
        });
      } catch (e) {
        console.error("Failed to parse run manifest", e);
      }
    }
  }, [data]);

  const onStepExpand = async (stepId: string) => {
    if (!run) return;
    const step = run.steps.find((s) => s.id === stepId);
    if (step && !step.output) {
      try {
        const markdown = await loadStep(pid, sid, workflowName, runId, stepId);
        setRun((prev) => {
          if (!prev) return null;
          return {
            ...prev,
            steps: prev.steps.map((s) =>
              s.id === stepId ? { ...s, output: markdown } : s
            ),
          };
        });
      } catch (e) {
        console.error("Failed to load step markdown", e);
      }
    }
  };

  if (isLoading) {
    return (
      <div style={{ padding: "20px", color: "var(--ink-soft)" }}>
        {t("app:loading")}
      </div>
    );
  }

  if (isError || !run) {
    return (
      <div style={{ padding: "20px", color: "oklch(0.42 0.14 22)" }}>
        {t("common:error")}
      </div>
    );
  }

  return <RunDetail run={run} onStepExpand={onStepExpand} t={t} />;
};

export default RunDetailContainer;
