"use client";

import { type CSSProperties, type FC, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useLatestSession } from "@/lib/useLatestSession";
import { getAdminAgents, getLibrary, listWorkflows, setAgentAugment, type AdminAgent } from "@/lib/api";
import { useEventStream, type SseEvent } from "@/lib/sse";
import { requestAgentSwitch, useCurrentAgent, useBusyAgent } from "@/lib/agentBus";
import { tokens } from "../_shared/armance-tokens";
import { PulseDot } from "../_shared/PulseDot";
import { assignAgentColour } from "@/lib/agent_colours";
import { emitViewChange, onViewChange, type ViewType } from "@/lib/navigationBus";

export interface SidebarNavProps {
  t: (key: string) => string;
}

const KEY_STAFF = "armance.sidebar.staff-open";
const KEY_ROLES = "armance.sidebar.roles-open";

function usePersistedOpen(key: string, fallback: boolean): [boolean, () => void] {
  const [open, setOpen] = useState(fallback);
  useEffect(() => {
    const v = localStorage.getItem(key);
    if (v != null) setOpen(v === "true");
  }, [key]);
  const toggle = () => setOpen((p) => {
    localStorage.setItem(key, String(!p));
    return !p;
  });
  return [open, toggle];
}

export const SidebarNav: FC<SidebarNavProps> = ({ t }) => {
  const { pid, sid } = useLatestSession();
  const [activeView, setActiveView] = useState<ViewType>("chat");
  // Which workflow is open (from the URL), so its sidebar sub-link highlights
  // instead of the parent "Workflows" entry.
  const [activeWorkflow, setActiveWorkflow] = useState<string>("");

  const readWorkflowFromPath = () => {
    if (typeof window === "undefined") return "";
    const segs = window.location.pathname.split("/").filter(Boolean);
    const i = segs.indexOf("workflows");
    const n = i >= 0 ? segs[i + 1] : "";
    return n && n !== "_" ? decodeURIComponent(n) : "";
  };

  useEffect(() => {
    setActiveWorkflow(readWorkflowFromPath());
    return onViewChange((v) => {
      setActiveView(v);
      setActiveWorkflow(v === "workflows" ? readWorkflowFromPath() : "");
    });
  }, []);

  const [staffOpen, toggleStaff] = usePersistedOpen(KEY_STAFF, true);
  const [rolesOpen, toggleRoles] = usePersistedOpen(KEY_ROLES, true);

  const currentAgent = useCurrentAgent();
  const busyAgent = useBusyAgent();

  const queryClient = useQueryClient();

  const { data: agents = [] } = useQuery({
    queryKey: ["sidebar-agents", pid, sid],
    enabled: Boolean(pid && sid),
    queryFn: () => getAdminAgents(pid, sid as string).catch(() => []),
  });

  // Refresh the roster when Malik recruits — otherwise the sidebar only
  // updated on a full page reload. The backend emits `agents.proposed` once
  // the specialist files are written.
  const handleSse = useCallback((evt: SseEvent) => {
    if (evt.name === "agents.proposed") {
      void queryClient.invalidateQueries({ queryKey: ["sidebar-agents", pid, sid] });
    }
  }, [queryClient, pid, sid]);
  useEventStream(pid, sid || "", handleSse);

  const staff = agents.filter((a) => a.staff);
  const specialists = agents.filter((a) => !a.staff);

  // Manual augment toggle — user-driven, deterministic. Optimistically flips
  // the cached roster so the glow responds instantly, then refetches.
  const onToggleAugment = useCallback(
    async (slug: string, next: boolean) => {
      if (!sid) return;
      try {
        await setAgentAugment(pid, sid as string, slug, next);
      } catch (err) {
        console.error("augment toggle failed", err);
      } finally {
        void queryClient.invalidateQueries({ queryKey: ["sidebar-agents", pid, sid] });
      }
    },
    [pid, sid, queryClient],
  );

  const { data: library } = useQuery({
    queryKey: ["sidebar-library", pid, sid],
    enabled: Boolean(pid && sid),
    refetchInterval: 4000,
    queryFn: () => getLibrary(pid, sid as string).catch(() => null),
  });

  // Designed workflows, listed under the Workflows section as shortcuts to
  // their visualization. Polled so a freshly designed workflow appears
  // without a reload (no dedicated workflow-created event exists).
  const { data: workflowsData } = useQuery({
    queryKey: ["sidebar-workflows", pid, sid],
    enabled: Boolean(pid && sid),
    refetchInterval: 4000,
    queryFn: () => listWorkflows(pid, sid as string).catch(() => null),
  });
  const workflows = workflowsData?.workflows ?? [];

  const onConversation = activeView === "chat";

  const isTabActive = (tab: string): boolean => {
    if (tab === "workflows") return activeView === "workflows";
    if (tab === "library") return activeView === "library";
    if (tab === "admin") return activeView === "admin";
    return false;
  };

  const handleNav = (e: React.MouseEvent, targetPath: string, view: ViewType) => {
    e.preventDefault();
    window.history.pushState(null, "", targetPath);
    emitViewChange(view);
  };

  const sessionPath = (suffix = "") => `/projects/${pid}/sessions/${sid || "_"}${suffix}`;

  /* ── Styles ── */
  const sectionHeader: CSSProperties = {
    fontFamily: tokens.ffMono, fontSize: "9px", letterSpacing: "0.14em",
    textTransform: "uppercase", color: tokens.inkFaint,
    padding: "16px 20px 6px", fontWeight: 600, userSelect: "none",
  };
  const collapsibleHeader: CSSProperties = {
    ...sectionHeader, display: "flex", alignItems: "center",
    justifyContent: "space-between", cursor: "pointer", background: "none",
    border: "none", width: "100%", textAlign: "left",
  };
  const navContainer: CSSProperties = {
    display: "flex", flexDirection: "column", gap: "2px", padding: "0 12px",
  };
  const link = (active: boolean): CSSProperties => ({
    display: "block", padding: "8px 12px", borderRadius: tokens.radiusSm,
    fontSize: "13px", fontFamily: tokens.ffSans,
    color: active ? tokens.accent : tokens.inkSoft,
    background: active ? "color-mix(in srgb, var(--accent) 8%, transparent)" : "transparent",
    textDecoration: "none", fontWeight: active ? 500 : 400,
    transition: "background 120ms ease, color 120ms ease", cursor: "pointer",
  });

  // Library subtitle, TUI-style: doc + feuillet counts, or inactive note when
  // no embedding model is configured.
  const librarySubtitle = (): string => {
    if (library && !library.embedding_model) return t("sidebar:library.inactive");
    const docs = library?.doc_count ?? 0;
    const fe = library?.total_feuillets ?? 0;
    return t("sidebar:library.subtitle")
      .replace("{docs}", String(docs))
      .replace("{feuillets}", String(fe));
  };

  // Agent click (anywhere): go to the conversation and switch to that agent.
  // The chat container stays mounted across tabs, so the agentBus switch reaches
  // it whatever the active view — no `?switch=` URL relay (which used to double-
  // fire alongside the bus and stack 2-3 "interlocuteur" separators).
  const onAgentClick = (firstName: string) => {
    if (!onConversation && sid) {
      window.history.pushState(null, "", sessionPath());
      emitViewChange("chat");
    }
    requestAgentSwitch(firstName);
  };

  // Open a specific workflow's visualization (mirrors WorkflowsList nav).
  const openWorkflow = (e: React.MouseEvent, name: string) => {
    e.preventDefault();
    if (!sid) return;
    window.history.pushState(null, "", sessionPath(`/workflows/${encodeURIComponent(name)}`));
    setActiveWorkflow(name);
    emitViewChange("workflows");
  };

  const agentRow = (a: AdminAgent, isStaff: boolean) => {
    const active = currentAgent === (a.slug ?? a.name) || currentAgent === a.name;
    const thinking = busyAgent === a.name;
    const reachable = Boolean(a.model);
    const agentColour = assignAgentColour(a.name);
    const discColour = reachable ? agentColour : `color-mix(in srgb, ${agentColour} 40%, transparent)`;
    // Staff carry a canonical role (weaver/scout/conductor/distiller/critic) that
    // is localized; specialists carry a free-form domain label, shown verbatim.
    const roleLabel = isStaff ? t(`roles:${a.role}`) : a.role;
    const canAugment = Boolean(a.is_boostable);
    const augmented = Boolean(a.boosted);
    return (
      <div
        key={a.slug ?? a.name}
        style={{ display: "flex", alignItems: "center", gap: 4, width: "100%" }}
      >
        <button
          style={{ ...link(active), display: "flex", alignItems: "center", gap: 8, background: active ? undefined : "none", border: "none", flex: 1, minWidth: 0 }}
          onClick={() => onAgentClick(a.name)}
          title={t("sidebar:staff.switch_hint")}
          aria-pressed={active}
        >
          <PulseDot size={8} color={discColour} active={thinking} />
          <span
            className={augmented ? "ae-augment-glow" : undefined}
            style={{
              flex: 1,
              textAlign: "left",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
              color: augmented ? tokens.accent : undefined,
              fontWeight: augmented ? 600 : undefined,
            }}
          >
            {a.name}
          </span>
          <span style={{ color: tokens.inkFaint, fontSize: 11, textAlign: "right", flexShrink: 0 }}>{roleLabel}</span>
        </button>
        {canAugment && (
          <button
            type="button"
            className={augmented ? "ae-augment-btn ae-augment-btn-on" : "ae-augment-btn"}
            onClick={() => { void onToggleAugment(a.slug ?? a.name, !augmented); }}
            aria-pressed={augmented}
            title={augmented ? t("sidebar:augment.active_hint") : t("sidebar:augment.hint")}
            aria-label={augmented ? t("sidebar:augment.active_hint") : t("sidebar:augment.hint")}
          >
            {/* upward chevrons — "augment". Sober, accent-tinted, no emoji. */}
            <svg width="11" height="11" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M3 8l4-4 4 4" />
              <path d="M3 11l4-4 4 4" />
            </svg>
          </button>
        )}
      </div>
    );
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", width: "100%" }}>
      <style>{`
        /* Augment toggle — ghost button, accent on hover/active (DESIGN.md). */
        .ae-augment-btn {
          display: flex; align-items: center; justify-content: center;
          width: 20px; height: 20px; flex-shrink: 0; padding: 0;
          border: none; border-radius: 4px; background: transparent;
          color: var(--ink-faint, #9c8e7e); cursor: pointer;
          opacity: 0.55; transition: color .15s ease, opacity .15s ease, background .15s ease;
        }
        .ae-augment-btn:hover { color: var(--accent, #6b4f8a); opacity: 1; background: color-mix(in srgb, var(--accent) 9%, transparent); }
        .ae-augment-btn-on { color: var(--accent, #6b4f8a); opacity: 1; }
        /* Soft violet glow on the augmented agent's name — reuses a gentle
           1s alternate pulse, accent only, no saturated colour. */
        .ae-augment-glow {
          animation: ae-augment-glow-kf 1.4s ease-in-out infinite alternate;
          text-shadow: 0 0 5px color-mix(in srgb, var(--accent) 45%, transparent);
        }
        @keyframes ae-augment-glow-kf {
          from { text-shadow: 0 0 3px color-mix(in srgb, var(--accent) 25%, transparent); }
          to   { text-shadow: 0 0 8px color-mix(in srgb, var(--accent) 60%, transparent); }
        }
        @media (prefers-reduced-motion: reduce) { .ae-augment-glow { animation: none; } }
      `}</style>
      {/* 1 · Library — L0 with TUI-style subtitle, no sub-items */}
      <p style={sectionHeader}>{t("sidebar:section.library")}</p>
      <nav style={navContainer}>
        <Link
          href={sid ? sessionPath("/library") : "#"}
          style={{ ...link(isTabActive("library")), display: "flex", flexDirection: "column", gap: 2, alignItems: "flex-start" }}
          onClick={(e) => {
            if (!sid) {
              e.preventDefault();
              return;
            }
            handleNav(e, sessionPath("/library"), "library");
          }}
        >
          <span>{t("sidebar:tabs.library")}</span>
          <span style={{ color: tokens.inkFaint, fontFamily: tokens.ffMono, fontSize: 10 }}>
            {librarySubtitle()}
          </span>
        </Link>
      </nav>

      {/* 2 · Staff — permanent team; click = switch + go to conversation */}
      <button style={collapsibleHeader} onClick={toggleStaff} aria-expanded={staffOpen}>
        <span>{t("sidebar:section.staff")}</span>
        <span aria-hidden="true" style={{ fontSize: "18px", fontWeight: "bold", display: "inline-flex", alignItems: "center", transform: "translateY(-2px)" }}>{staffOpen ? "▾" : "▸"}</span>
      </button>
      {staffOpen && (
        <nav style={navContainer}>
          {staff.length === 0 && (
            <span style={{ ...link(false), color: tokens.inkFaint, fontStyle: "italic", cursor: "default" }}>
              {t("sidebar:staff.empty")}
            </span>
          )}
          {staff.map((a) => agentRow(a, true))}
        </nav>
      )}

      {/* 3 · Roles & agents — recruited specialists; click = @mention */}
      {specialists.length > 0 && (
        <>
          <button style={collapsibleHeader} onClick={toggleRoles} aria-expanded={rolesOpen}>
            <span>{t("sidebar:section.roles")}</span>
            <span aria-hidden="true" style={{ fontSize: "18px", fontWeight: "bold", display: "inline-flex", alignItems: "center", transform: "translateY(-2px)" }}>{rolesOpen ? "▾" : "▸"}</span>
          </button>
          {rolesOpen && (
            <nav style={navContainer}>
              {specialists.map((a) => agentRow(a, false))}
            </nav>
          )}
        </>
      )}

      {/* 4 · Workspace — Workflows only */}
      <p style={sectionHeader}>{t("sidebar:nav_section.workspace")}</p>
      <nav style={navContainer}>
        <Link
          href={sid ? sessionPath("/workflows/_") : "#"}
          // Parent highlights only on the workflows index (no specific workflow).
          style={link(isTabActive("workflows") && !activeWorkflow)}
          onClick={(e) => {
            if (!sid) {
              e.preventDefault();
              return;
            }
            setActiveWorkflow("");
            handleNav(e, sessionPath("/workflows/_"), "workflows");
          }}
        >
          {t("sidebar:tabs.workflows")}
        </Link>
        {workflows.map((w) => {
          const wfActive = isTabActive("workflows") && activeWorkflow === w.name;
          return (
            <a
              key={w.name}
              href={sid ? sessionPath(`/workflows/${encodeURIComponent(w.name)}`) : "#"}
              onClick={(e) => openWorkflow(e, w.name)}
              data-testid={`sidebar-workflow-${w.name}`}
              title={w.scope || w.name}
              aria-current={wfActive ? "page" : undefined}
              style={{
                ...link(wfActive),
                paddingLeft: 28,
                fontSize: "12px",
                color: wfActive ? tokens.accent : tokens.inkSoft,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {w.name}
            </a>
          );
        })}
      </nav>

      {/* 5 · Admin */}
      <p style={sectionHeader}>{t("sidebar:nav_section.account")}</p>
      <nav style={navContainer}>
        <Link
          href={`/projects/${pid}/admin`}
          style={link(isTabActive("admin"))}
          onClick={(e) => handleNav(e, `/projects/${pid}/admin`, "admin")}
        >
          {t("sidebar:tabs.settings")}
        </Link>
      </nav>
    </div>
  );
};

export default SidebarNav;
