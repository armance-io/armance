"use client";

import { type ReactNode, useEffect, useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { AppShell } from "@/components/visual/AppShell";
import { usePathname } from "next/navigation";
import { onViewChange, type ViewType } from "@/lib/navigationBus";

// Dynamic view components
import SessionView from "./sessions/[sid]/SessionView";
import LibraryView from "./sessions/[sid]/library/LibraryView";
import WorkflowView from "./sessions/[sid]/workflows/[name]/WorkflowView";
import AdminPageContainer from "@/components/admin/AdminPageContainer";

export default function ProjectLayout({ children: _children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const pathname = usePathname() ?? "";

  // Resolve initial view from URL path on cold start
  const initialView = useMemo<ViewType>(() => {
    if (pathname.includes("/library")) return "library";
    if (pathname.includes("/workflows")) return "workflows";
    if (pathname.includes("/admin")) return "admin";
    return "chat";
  }, [pathname]);

  const [activeView, setActiveView] = useState<ViewType>(initialView);

  useEffect(() => {
    setActiveView(initialView);
  }, [initialView]);

  // Subscribe to soft navigation bus events
  useEffect(() => {
    return onViewChange((view) => {
      setActiveView(view);
    });
  }, []);

  const pidMatch = pathname.match(/\/projects\/([^/]+)/);
  const pid = pidMatch ? pidMatch[1] : "default";

  return (
    <AppShell t={t}>
      {activeView === "library" && <LibraryView />}
      {activeView === "workflows" && <WorkflowView />}
      {activeView === "admin" && <AdminPageContainer pid={pid || "default"} t={t} />}
      {activeView === "chat" && <SessionView />}
    </AppShell>
  );
}
