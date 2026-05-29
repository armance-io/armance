/**
 * Footprint API types, fetch wrapper, and data hook.
 *
 * EI.8 structural half — data wiring only.
 * Visual components (FootprintChip, FootprintTab, Méthode expander)
 * are generated via Claude Design (web-v2-claude-design-prompts.md) and
 * wired here after hand-off.
 *
 * Live header chip is blocked on Epic C (SSE ledger-snapshot channel).
 */

import { useEffect, useState } from "react";
import { api } from "./api";

// ---------------------------------------------------------------------------
// Types (mirror EI.7 backend response exactly)
// ---------------------------------------------------------------------------

export interface FootprintBucket {
  gco2e: number;
  water_ml: number;
  calls: number;
  has_estimate: boolean;
  has_unknown: boolean;
}

export type GroupBy = "agent" | "day" | "month" | "session";

export interface FootprintResponse {
  by_agent: Record<string, FootprintBucket>;
  by_day: Record<string, FootprintBucket>;
  by_month: Record<string, FootprintBucket>;
  by_session: Record<string, FootprintBucket>;
  dominant_zone: string | null;
}

// ---------------------------------------------------------------------------
// API wrapper
// ---------------------------------------------------------------------------

export async function getFootprint(
  pid: string,
  groupBy: GroupBy = "agent",
): Promise<FootprintResponse> {
  return api.get<FootprintResponse>(
    `/projects/${pid}/admin/footprint?group_by=${groupBy}`,
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export interface UseFootprintResult {
  data: FootprintResponse | null;
  loading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useFootprint(
  pid: string,
  groupBy: GroupBy = "agent",
): UseFootprintResult {
  const [data, setData] = useState<FootprintResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [rev, setRev] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getFootprint(pid, groupBy)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [pid, groupBy, rev]);

  return { data, loading, error, refetch: () => setRev((r) => r + 1) };
}
