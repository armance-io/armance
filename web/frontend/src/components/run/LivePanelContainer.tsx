"use client";

import { type FC } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { getRunArguments, getRunSources, getRunHypotheses } from "@/lib/api";
import { useLiveManifest } from "@/lib/useLiveManifest";
import { LivePanel } from "./LivePanel";

export interface LivePanelContainerProps {
  pid: string;
  sid: string;
  workflowName: string;
  runId: string;
}

export const LivePanelContainer: FC<LivePanelContainerProps> = ({
  pid,
  sid,
  workflowName,
  runId,
}) => {
  const { t } = useTranslation();

  // 1. Fetch live manifest run polling data
  const { data: runFiles, isLoading: manifestLoading } = useLiveManifest(
    pid,
    sid,
    workflowName,
    runId
  );

  // 2. Fetch arguments, sources, and hypotheses in parallel
  const { data: argsData, isLoading: argsLoading } = useQuery({
    queryKey: ["run-arguments", pid, sid, workflowName, runId],
    queryFn: () => getRunArguments(pid, sid, workflowName, runId),
  });

  const { data: sourcesData, isLoading: sourcesLoading } = useQuery({
    queryKey: ["run-sources", pid, sid, workflowName, runId],
    queryFn: () => getRunSources(pid, sid, workflowName, runId),
  });

  const { data: hypothesesData, isLoading: hypothesesLoading } = useQuery({
    queryKey: ["run-hypotheses", pid, sid, workflowName, runId],
    queryFn: () => getRunHypotheses(pid, sid, workflowName, runId),
  });

  const isLoading = manifestLoading || argsLoading || sourcesLoading || hypothesesLoading;

  if (isLoading) {
    return (
      <div
        style={{
          width: "420px",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
          fontStyle: "italic",
          color: "var(--ink-soft, #5b5145)",
          borderLeft: "1px solid var(--rule, #d6c8ad)",
          background: "var(--bg-paper, #f4ede0)",
        }}
      >
        {t("run:panel.loading")}
      </div>
    );
  }

  // Parse manifest
  const runManifest = runFiles && runFiles["manifest.json"]
    ? JSON.parse(runFiles["manifest.json"])
    : null;

  const mode = runManifest?.mode || "autonomous";

  // Search runFiles file records for compiled synthesis/deliverable Markdown
  const deliverableMarkdown = runFiles
    ? runFiles["deliverable.md"] || runFiles["synthesis.md"] || ""
    : "";

  const deliverable = {
    title: runManifest ? `${workflowName} — Deliverable` : "Deliverable",
    markdown: deliverableMarkdown || `# ${t("run:panel.compiling")}\n\n${t("run:panel.compiling_desc")}`,
    downloadUrl: `/api/projects/${pid}/sessions/${sid}/workflows/${encodeURIComponent(workflowName)}/runs/${encodeURIComponent(runId)}/deliverable`,
    format: "md" as const,
  };

  const args = argsData?.arguments || [];
  const sources = sourcesData?.sources || [];
  const hypotheses = hypothesesData?.hypotheses || [];

  // Compose dynamic export download links
  const downloads: { format: string; url: string }[] = [];
  if (runFiles) {
    if (runFiles["deliverable.pdf"]) {
      downloads.push({
        format: "PDF",
        url: `/api/projects/${pid}/sessions/${sid}/exports/${encodeURIComponent(workflowName)}/${encodeURIComponent(runId)}/deliverable.pdf`,
      });
    }
    if (runFiles["deliverable.md"]) {
      downloads.push({
        format: "MD",
        url: `/api/projects/${pid}/sessions/${sid}/exports/${encodeURIComponent(workflowName)}/${encodeURIComponent(runId)}/deliverable.md`,
      });
    } else if (runFiles["synthesis.md"]) {
      downloads.push({
        format: "MD",
        url: `/api/projects/${pid}/sessions/${sid}/exports/${encodeURIComponent(workflowName)}/${encodeURIComponent(runId)}/synthesis.md`,
      });
    }
  }

  return (
    <LivePanel
      mode={mode}
      deliverable={deliverable}
      arguments={args as unknown as Parameters<typeof LivePanel>[0]["arguments"]}
      sources={sources as unknown as Parameters<typeof LivePanel>[0]["sources"]}
      hypotheses={hypotheses as unknown as Parameters<typeof LivePanel>[0]["hypotheses"]}
      downloads={downloads}
      t={t}
    />
  );
};

export default LivePanelContainer;
