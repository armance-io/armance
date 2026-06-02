"use client";

import { type CSSProperties, type FC, useEffect, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useLatestSession } from "@/lib/useLatestSession";
import { getAdminAgents, getLibrary } from "@/lib/api";
import { emitMention } from "@/lib/mentionBus";
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

  useEffect(() => {
    return onViewChange((v) => {
      setActiveView(v);
    });
  }, []);

  const [staffOpen, toggleStaff] = usePersistedOpen(KEY_STAFF, true);
  const [rolesOpen, toggleRoles] = usePersistedOpen(KEY_ROLES, true);

  const currentAgent = useCurrentAgent();
  const busyAgent = useBusyAgent();

  const { data: agents = [] } = useQuery({
    queryKey: ["sidebar-agents", pid, sid],
    enabled: Boolean(pid && sid),
    queryFn: () => getAdminAgents(pid, sid as string).catch(() => []),
  });

  const staff = agents.filter((a) => a.staff);
  const specialists = agents.filter((a) => !a.staff);

  const { data: library } = useQuery({
    queryKey: ["sidebar-library", pid, sid],
    enabled: Boolean(pid && sid),
    refetchInterval: 4000,
    queryFn: () => getLibrary(pid, sid as string).catch(() => null),
  });

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

  const agentRow = (a: { name: string; slug?: string; role: string; model?: string }, isStaff: boolean) => {
    const active = isStaff && (currentAgent === (a.slug ?? a.name) || currentAgent === a.name);
    const thinking = busyAgent === a.name;
    const reachable = Boolean(a.model);
    const agentColour = assignAgentColour(a.name);
    const discColour = reachable ? agentColour : `color-mix(in srgb, ${agentColour} 40%, transparent)`;
    // Staff carry a canonical role (weaver/scout/conductor/distiller/critic) that
    // is localized; specialists carry a free-form domain label, shown verbatim.
    const roleLabel = isStaff ? t(`roles:${a.role}`) : a.role;
    return (
      <button
        key={a.slug ?? a.name}
        style={{ ...link(active), display: "flex", alignItems: "center", gap: 8, background: active ? undefined : "none", border: "none", width: "100%" }}
        onClick={() => (isStaff ? onAgentClick(a.name) : emitMention(a.name))}
        title={isStaff ? t("sidebar:staff.switch_hint") : t("sidebar:staff.mention_hint")}
        aria-pressed={active}
      >
        <PulseDot size={8} color={discColour} active={thinking} />
        <span style={{ flex: 1, textAlign: "left" }}>{a.name}</span>
        <span style={{ color: tokens.inkFaint, fontSize: 11, textAlign: "right" }}>{roleLabel}</span>
      </button>
    );
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", width: "100%" }}>
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
          style={link(isTabActive("workflows"))}
          onClick={(e) => {
            if (!sid) {
              e.preventDefault();
              return;
            }
            handleNav(e, sessionPath("/workflows/_"), "workflows");
          }}
        >
          {t("sidebar:tabs.workflows")}
        </Link>
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
