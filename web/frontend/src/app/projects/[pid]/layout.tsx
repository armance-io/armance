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
import DeliverablesView from "./sessions/[sid]/deliverables/DeliverablesView";
import AdminPageContainer from "@/components/admin/AdminPageContainer";

export default function ProjectLayout({ children: _children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const pathname = usePathname() ?? "";

  // Resolve initial view from URL path on cold start
  const initialView = useMemo<ViewType>(() => {
    if (pathname.includes("/library")) return "library";
    if (pathname.includes("/workflows")) return "workflows";
    if (pathname.includes("/admin")) return "admin";
    if (pathname.includes("/deliverables")) return "deliverables";
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

  const isSubpage = pathname.includes("/runs/") || pathname.includes("/preview");
  const isChatActive = activeView === "chat" && !isSubpage;

  return (
    <AppShell t={t}>
      {/* Chat stays mounted across tab switches: this preserves its local state
          (agent-switch separators) AND keeps the SSE EventSource alive, so a
          turn.completed emitted while another tab is showing is never lost (the
          cause of the recurring stuck-input + vanishing-separator bugs). When
          active it uses `contents` so the chat section's height:100% still
          resolves against <main>; when inactive it is fully removed from layout
          with `none`. The other views carry no ephemeral state and refetch on
          mount, so they stay conditionally mounted. */}
      <div style={{ display: isChatActive ? "contents" : "none" }}>
        <SessionView active={isChatActive} />
      </div>
      {isSubpage ? (
        _children
      ) : (
        <>
          {activeView === "library" && <LibraryView />}
          {activeView === "workflows" && <WorkflowView />}
          {activeView === "deliverables" && <DeliverablesView />}
          {activeView === "admin" && <AdminPageContainer pid={pid || "default"} t={t} />}
        </>
      )}
    </AppShell>
  );
}
