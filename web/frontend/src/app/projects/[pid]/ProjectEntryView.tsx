"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { useRouteParams } from "@/lib/routeParams";

/**
 * Project entry point. The launcher navigates here (/projects/{pid}); this
 * resolves the project's latest session and lands on it. Without this route a
 * bare /projects/{pid} fell through to the home shell, which hard-codes the
 * "default" project — so opening project B silently opened "default".
 *
 * The real pid comes from the URL (useRouteParams), not the build-time
 * sentinel param.
 */
export default function ProjectEntryView() {
  const { t } = useTranslation();
  const { pid } = useRouteParams();
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!pid || pid === "_") return;
    fetch(`/api/projects/${pid}/sessions/latest`, { credentials: "include" })
      .then((res) => {
        if (!res.ok) throw new Error(String(res.status));
        return res.json();
      })
      .then((data) => {
        if (data && data.id) {
          window.location.replace(`/projects/${pid}/sessions/${data.id}`);
        } else {
          setError(true);
        }
      })
      .catch(() => setError(true));
  }, [pid]);

  return (
    <main className="launcher-root" data-testid="project-entry">
      <div className="launcher-body">
        {error ? (
          <p className="launcher-error" data-testid="project-entry-error">
            {t("launcher:error.open_failed")}
          </p>
        ) : (
          <p className="launcher-subtitle">{t("app:loading")}</p>
        )}
      </div>
    </main>
  );
}
