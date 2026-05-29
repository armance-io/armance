"use client";

import { type FC } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";
import { listRuns, deleteRun, type RunItem } from "@/lib/api";
import { RunHistory } from "./RunHistory";

export interface RunHistoryContainerProps {
  pid: string;
  sid: string;
  workflowName: string;
}

export const RunHistoryContainer: FC<RunHistoryContainerProps> = ({
  pid,
  sid,
  workflowName,
}) => {
  const { t } = useTranslation();
  const router = useRouter();
  const queryClient = useQueryClient();

  // Query workflow runs list from the backend
  const { data: runs = [] } = useQuery<RunItem[]>({
    queryKey: ["runs-list", pid, sid, workflowName],
    queryFn: () => listRuns(pid, sid, workflowName),
    refetchInterval: 5000, // Poll list changes every 5 seconds
  });

  const handleOpen = (runId: string) => {
    router.push(
      `/projects/${pid}/sessions/${sid}/workflows/${encodeURIComponent(workflowName)}/runs/${encodeURIComponent(runId)}`
    );
  };

  const handleDelete = async (runId: string) => {
    await deleteRun(pid, sid, workflowName, runId);
    // Invalidate historical lists to trigger instant refresh
    queryClient.invalidateQueries({ queryKey: ["runs-list", pid, sid, workflowName] });
  };

  return (
    <RunHistory
      runs={runs}
      onOpen={handleOpen}
      onDelete={handleDelete}
      t={t}
    />
  );
};

export default RunHistoryContainer;
