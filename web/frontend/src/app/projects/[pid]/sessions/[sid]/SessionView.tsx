"use client";

import { useTranslation } from "react-i18next";
import { AppShell } from "@/components/visual/AppShell";
import { ChatStreamContainer } from "@/components/chat/ChatStreamContainer";
import { EmptySession } from "@/components/visual/EmptyState/EmptySession";
import { useRouteParams } from "@/lib/routeParams";

export default function SessionView() {
  const { pid, sid } = useRouteParams();
  const { t } = useTranslation();

  if (!pid || !sid) {
    return (
      <AppShell t={t}>
        <EmptySession t={t} />
      </AppShell>
    );
  }

  return (
    <AppShell t={t}>
      <ChatStreamContainer pid={pid} sid={sid} />
    </AppShell>
  );
}
