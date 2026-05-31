"use client";

import { useQuery } from "@tanstack/react-query";
import { getAdminStats } from "./api";
import { getFootprint } from "./footprint";

export interface SessionMetrics {
  tokensIn: number;
  tokensOut: number;
  gco2e: number;
  waterMl: number;
  hasEstimate: boolean;
}

/**
 * Live session metrics for the header strip (TUI parity): tokens in/out +
 * environmental footprint. Polls every 2 s so the values track an ongoing
 * deliberation without a manual refresh. Same data sources as Settings →
 * Statistics / Empreinte (factored, not duplicated).
 */
export function useSessionMetrics(pid: string | undefined): SessionMetrics {
  const { data } = useQuery({
    queryKey: ["session-metrics", pid],
    enabled: Boolean(pid),
    refetchInterval: 2000,
    queryFn: async () => {
      const [stats, footprint] = await Promise.all([
        getAdminStats(pid as string).catch(() => null),
        getFootprint(pid as string, "session").catch(() => null),
      ]);
      const g = stats?.global;
      const buckets = footprint ? Object.values(footprint.by_session) : [];
      const gco2e = buckets.reduce((s, b) => s + (b.gco2e ?? 0), 0);
      const waterMl = buckets.reduce((s, b) => s + (b.water_ml ?? 0), 0);
      const hasEstimate = buckets.some((b) => b.has_estimate);
      return {
        tokensIn: g?.tokens_in ?? 0,
        tokensOut: g?.tokens_out ?? 0,
        gco2e,
        waterMl,
        hasEstimate,
      } satisfies SessionMetrics;
    },
  });

  return data ?? { tokensIn: 0, tokensOut: 0, gco2e: 0, waterMl: 0, hasEstimate: false };
}
