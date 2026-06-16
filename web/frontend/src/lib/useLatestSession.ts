import { useEffect, useState } from "react";
import { useRouteParams } from "./routeParams";

export interface SessionInfo {
  pid: string;
  sid: string | null;
  loading: boolean;
}

export function useLatestSession(): SessionInfo {
  const { pid = "default", sid: urlSid } = useRouteParams();
  const [sid, setSid] = useState<string | null>(urlSid || null);
  const [loading, setLoading] = useState<boolean>(!urlSid);

  useEffect(() => {
    if (urlSid) {
      setSid(urlSid);
      const storageKey = `armance.latest-session-id-${pid}`;
      if (typeof localStorage !== "undefined" && typeof localStorage.setItem === "function") {
        localStorage.setItem(storageKey, urlSid);
      }
      setLoading(false);
    } else {
      const storageKey = `armance.latest-session-id-${pid}`;
      const stored = typeof localStorage !== "undefined" && typeof localStorage.getItem === "function"
        ? localStorage.getItem(storageKey)
        : null;
      if (stored) {
        setSid(stored);
        setLoading(false);
      } else {
        setLoading(true);
        // Fallback to fetch latest session
        const targetPid = pid && pid !== "_" ? pid : "default";
        fetch(`/api/projects/${targetPid}/sessions/latest`)
          .then((res) => (res.ok ? res.json() : null))
          .then((data) => {
            if (data && data.id) {
              setSid(data.id);
              if (typeof localStorage !== "undefined" && typeof localStorage.setItem === "function") {
                localStorage.setItem(storageKey, data.id);
              }
            }
          })
          .catch(console.error)
          .finally(() => setLoading(false));
      }
    }
  }, [urlSid, pid]);

  return { pid, sid, loading };
}
