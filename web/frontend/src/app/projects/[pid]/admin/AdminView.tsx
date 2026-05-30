"use client";

import { useTranslation } from "react-i18next";
import { AppShell } from "@/components/visual/AppShell";
import { EmptyShell } from "@/components/visual/EmptyState/EmptyShell";
import AdminPageContainer from "@/components/admin/AdminPageContainer";
import { useRouteParams } from "@/lib/routeParams";

export default function AdminView() {
  const { pid } = useRouteParams();
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
