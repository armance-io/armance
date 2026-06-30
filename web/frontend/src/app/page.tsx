"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { AppShell } from "@/components/visual/AppShell";
import { EmptySession } from "@/components/visual/EmptyState/EmptySession";
import { createSession, getSetupStatus } from "@/lib/api";

export default function HomePage() {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getSetupStatus()
      .then((status) => {
        if (!status.configured) {
          window.location.replace("/setup");
          return;
        }
        // Proceed with latest session
        return fetch("/api/projects/default/sessions/latest")
          .then((res) => {
            if (!res.ok) throw new Error("Failed to fetch latest session");
            return res.json();
          })
          .then(async (data) => {
            // Always land inside a session: that surface mounts the chat
            // container (prefill listener), the agent roster, and the Library
            // links. The bare home page has no session, so its empty-state
            // buttons and "Armance" click had nothing to act on. Resume the
            // latest session, or create one on first visit.
            const id = data?.id ?? (await createSession("default")).id;
            window.location.replace(`/projects/default/sessions/${id}`);
          });
      })
      .catch((err) => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div style={{
        display: "flex",
        height: "100vh",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--bg-paper, #f4ede0)",
        color: "var(--ink-soft, #5b5145)",
        fontFamily: "var(--ff-sans, sans-serif)",
        fontSize: "14px",
      }}>
        {t("app:loading")}
      </div>
    );
  }

  return (
    <AppShell t={t}>
      <EmptySession t={t} />
    </AppShell>
  );
}
