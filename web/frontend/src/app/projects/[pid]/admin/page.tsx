"use client";

import { use, useState } from "react";
import { useTranslation } from "react-i18next";
import { AppShell } from "@/components/visual/AppShell";
import { EmptyShell } from "@/components/visual/EmptyState/EmptyShell";
import AdminPageContainer from "@/components/admin/AdminPageContainer";

interface AdminPageProps {
  params: Promise<{ pid: string }>;
}

export default function AdminPage({ params }: AdminPageProps) {
  const { pid } = use(params);
  const { t } = useTranslation();

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
      <AdminPageContainer pid={pid} t={t} />
    </AppShell>
  );
}
