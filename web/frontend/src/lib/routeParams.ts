"use client";

import { usePathname } from "next/navigation";

/**
 * Read route ids from the live URL instead of build-time params.
 *
 * Under static export (`output: "export"`) dynamic routes are pre-rendered
 * with a sentinel param ("_"). The real ids only exist in the browser URL,
 * so client views resolve them here rather than trusting the baked param.
 *
 * Route shape: /projects/{pid}/sessions/{sid}/... with optional
 * /workflows/{name}, /runs/{runId}.
 */
export interface RouteParams {
  pid: string;
  sid: string;
  name?: string | undefined;
  runId?: string | undefined;
}

export function useRouteParams(): RouteParams {
  const pathname = usePathname() ?? "";
  const segs = pathname.split("/").filter(Boolean);
  const at = (key: string): string | undefined => {
    const i = segs.indexOf(key);
    return i >= 0 && i + 1 < segs.length ? decodeURIComponent(segs[i + 1]!) : undefined;
  };
  // `name` follows /workflows/, `runId` follows /runs/.
  return {
    pid: at("projects") ?? "",
    sid: at("sessions") ?? "",
    name: at("workflows"),
    runId: at("runs"),
  };
}
