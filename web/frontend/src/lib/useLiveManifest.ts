import { useState, useEffect } from "react";
import { loadRun } from "./api";

export function useLiveManifest(
  pid: string,
  sid: string,
  workflowName: string,
  runId: string,
) {
  const [data, setData] = useState<Record<string, string> | null>(null);
  const [error, setError] = useState<unknown | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // No active run → don't poll. Polling with an empty runId hits `/runs/`
    // (trailing slash → 307 redirect) every second and floods the server log.
    if (!runId) {
      setData(null);
      setIsLoading(false);
      return;
    }

    let active = true;
    let timerId: ReturnType<typeof setInterval> | null = null;

    async function poll() {
      try {
        const result = await loadRun(pid, sid, workflowName, runId);
        if (!active) return;
        setData(result);
        setError(null);
        setIsLoading(false);

        // Stop polling once the run reaches a terminal state. The live run
        // status is "working" (canonical lifecycle string); anything else
        // (completed / failed / canceled) is terminal.
        if (result && result["manifest.json"]) {
          const manifest = JSON.parse(result["manifest.json"]);
          if (manifest.status !== "working") {
            if (timerId) {
              clearInterval(timerId);
              timerId = null;
            }
          }
        }
      } catch (err) {
        if (!active) return;
        setError(err);
        setIsLoading(false);
      }
    }

    // Initial load
    poll();

    // Poll every 1s
    timerId = setInterval(poll, 1000);

    return () => {
      active = false;
      if (timerId) clearInterval(timerId);
    };
  }, [pid, sid, workflowName, runId]);

  return { data, isLoading, isError: !!error, error };
}
