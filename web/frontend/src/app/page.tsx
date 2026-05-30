"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { AppShell } from "@/components/visual/AppShell";
import { EmptyShell } from "@/components/visual/EmptyState/EmptyShell";
import { EmptySession } from "@/components/visual/EmptyState/EmptySession";

export default function HomePage() {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/projects/default/sessions/latest")
      .then((res) => {
        if (!res.ok) throw new Error("Failed to fetch latest session");
        return res.json();
      })
      .then((data) => {
        if (data && data.id) {
          window.location.replace(`/projects/default/sessions/${data.id}/library`);
        } else {
          setLoading(false);
        }
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
        Chargement...
      </div>
    );
  }

  return (
    <AppShell
      sidebar={
        <EmptyShell
          title={t("visual:empty.shell.title")}
          hint={t("visual:empty.shell.hint")}
        />
      }
      t={t}
    >
      <EmptySession t={t} />
    </AppShell>
  );
}
