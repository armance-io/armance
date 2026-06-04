"use client";

import { type FC } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useLiveManifest } from "@/lib/useLiveManifest";
import { stopWorkflow } from "@/lib/api";
import { InterruptButton } from "./InterruptButton";

export interface InterruptButtonContainerProps {
  pid: string;
  sid: string;
  workflowName: string;
  runId: string;
}

export const InterruptButtonContainer: FC<InterruptButtonContainerProps> = ({
  pid,
  sid,
  workflowName,
  runId,
}) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  
  // Retrieve the dynamic live manifest to inspect the real-time status of the run
  const { data } = useLiveManifest(pid, sid, workflowName, runId);

  const runManifest = data && data["manifest.json"]
    ? JSON.parse(data["manifest.json"])
    : null;

  const status = runManifest ? runManifest.status : "running";

  const handleInterrupt = async () => {
    await stopWorkflow(pid, sid, workflowName);
    // Success: invalidate active workflow status and historical runs lists globally
    queryClient.invalidateQueries({ queryKey: ["active-workflow", pid, sid] });
    queryClient.invalidateQueries({ queryKey: ["runs-list", pid, sid, workflowName] });
  };

  return (
    <InterruptButton
      runId={runId}
      status={status}
      onInterrupt={handleInterrupt}
      t={t}
    />
  );
};

export default InterruptButtonContainer;
