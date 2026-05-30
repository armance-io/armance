"use client";

import { useTranslation } from "react-i18next";
import { AppShell } from "@/components/visual/AppShell";
import AdminPageContainer from "@/components/admin/AdminPageContainer";
import { useRouteParams } from "@/lib/routeParams";

export default function AdminView() {
  const { pid } = useRouteParams();
  const { t } = useTranslation();

  return (
    <AppShell t={t}>
      <AdminPageContainer pid={pid} t={t} />
    </AppShell>
  );
}
