"use client";

import { useTranslation } from "react-i18next";
import { ChatStreamContainer } from "@/components/chat/ChatStreamContainer";
import { EmptySession } from "@/components/visual/EmptyState/EmptySession";
import { useRouteParams } from "@/lib/routeParams";

export default function SessionView({ active = true }: { active?: boolean }) {
  const { pid, sid } = useRouteParams();
  const { t } = useTranslation();

  if (!pid || !sid) {
    if (!active) return null;
    return <EmptySession t={t} />;
  }
  return <ChatStreamContainer pid={pid} sid={sid} active={active} />;
}
