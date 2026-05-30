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
      localStorage.setItem("armance.latest-session-id", urlSid);
      setLoading(false);
    } else {
      const stored = localStorage.getItem("armance.latest-session-id");
      if (stored) {
        setSid(stored);
        setLoading(false);
      } else {
        setLoading(true);
        // Fallback to fetch latest session
        fetch("/api/projects/default/sessions/latest")
          .then((res) => (res.ok ? res.json() : null))
          .then((data) => {
            if (data && data.id) {
              setSid(data.id);
              localStorage.setItem("armance.latest-session-id", data.id);
            }
          })
          .catch(console.error)
          .finally(() => setLoading(false));
      }
    }
  }, [urlSid]);

  return { pid, sid, loading };
}
