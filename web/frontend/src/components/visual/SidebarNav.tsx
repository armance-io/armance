"use client";

import { type CSSProperties, type FC, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLatestSession } from "@/lib/useLatestSession";
import { getAdminAgents, getLibrary } from "@/lib/api";
import { emitMention } from "@/lib/mentionBus";
import { requestAgentSwitch, useCurrentAgent } from "@/lib/agentBus";
import { tokens } from "../_shared/armance-tokens";

export interface SidebarNavProps {
  t: (key: string) => string;
}

const KEY_STAFF = "armance.sidebar.staff-open";
const KEY_LIB = "armance.sidebar.library-open";

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
  const pathname = typeof window !== "undefined" ? window.location.pathname : "";

  const [staffOpen, toggleStaff] = usePersistedOpen(KEY_STAFF, true);
  const [libOpen, toggleLib] = usePersistedOpen(KEY_LIB, true);

  const currentAgent = useCurrentAgent();

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

  const isTabActive = (tab: string): boolean => {
    if (tab === "session")
      return /\/sessions\/[^/]+$/.test(pathname) &&
        !/(workflows|library|deliverables)/.test(pathname);
    if (tab === "workflows") return pathname.includes("/workflows");
    if (tab === "library") return pathname.includes("/library");
    if (tab === "deliverables") return pathname.includes("/deliverables");
    if (tab === "admin") return pathname.includes("/admin");
    return false;
  };

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
  const sessionPath = (suffix = "") => `/projects/${pid}/sessions/${sid || "_"}${suffix}`;

  const navLink = (tab: string, suffix: string, label: string) => (
    <a
      href={sid ? sessionPath(suffix) : "#"}
      style={link(isTabActive(tab))}
      onClick={(e) => { if (!sid) e.preventDefault(); }}
    >
      {label}
    </a>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", width: "100%" }}>
      {/* Workspace nav */}
      <p style={sectionHeader}>{t("sidebar:nav_section.workspace")}</p>
      <nav style={navContainer}>
        {navLink("session", "", t("sidebar:tabs.session_active"))}
        {navLink("workflows", "/workflows/_", t("sidebar:tabs.workflows"))}
        {navLink("library", "/library", t("sidebar:tabs.library"))}
        {navLink("deliverables", "/deliverables", t("sidebar:tabs.deliverables"))}
      </nav>

      {/* Staff / Roles — click injects @Agent into the chat input */}
      <button style={collapsibleHeader} onClick={toggleStaff} aria-expanded={staffOpen}>
        <span>{t("sidebar:section.staff")}</span>
        <span aria-hidden="true">{staffOpen ? "▾" : "▸"}</span>
      </button>
      {staffOpen && (
        <nav style={navContainer}>
          {staff.length === 0 && (
            <span style={{ ...link(false), color: tokens.inkFaint, fontStyle: "italic", cursor: "default" }}>
              {t("sidebar:staff.empty")}
            </span>
          )}
          {staff.map((a) => {
            const active = currentAgent === (a.slug ?? a.name) || currentAgent === a.name;
            return (
              <button
                key={a.slug ?? a.name}
                style={{ ...link(active), display: "flex", justifyContent: "space-between", gap: 8, border: "none" }}
                onClick={() => requestAgentSwitch(a.name)}
                title={t("sidebar:staff.switch_hint")}
                aria-pressed={active}
              >
                <span>{a.name}</span>
                <span style={{ color: tokens.inkFaint, fontSize: 11 }}>{a.role}</span>
              </button>
            );
          })}
        </nav>
      )}

      {/* Roles & agents — recruited specialists; click injects @mention */}
      {specialists.length > 0 && (
        <>
          <p style={sectionHeader}>{t("sidebar:section.roles")}</p>
          <nav style={navContainer}>
            {specialists.map((a) => (
              <button
                key={a.slug ?? a.name}
                style={{ ...link(false), display: "flex", justifyContent: "space-between", gap: 8, background: "none", border: "none" }}
                onClick={() => emitMention(a.name)}
                title={t("sidebar:staff.mention_hint")}
              >
                <span>{a.name}</span>
                <span style={{ color: tokens.inkFaint, fontSize: 11 }}>{a.role}</span>
              </button>
            ))}
          </nav>
        </>
      )}

      {/* Library — docs + feuillet counts */}
      <button style={collapsibleHeader} onClick={toggleLib} aria-expanded={libOpen}>
        <span>{t("sidebar:section.library")}</span>
        <span aria-hidden="true">{libOpen ? "▾" : "▸"}</span>
      </button>
      {libOpen && (
        <div style={{ ...navContainer, gap: 4 }}>
          <a href={sid ? sessionPath("/library") : "#"} style={{ ...link(false), display: "flex", justifyContent: "space-between" }}>
            <span>{t("sidebar:library.docs")}</span>
            <span style={{ color: tokens.inkFaint, fontFamily: tokens.ffMono, fontSize: 11 }}>
              {library?.doc_count ?? 0}
            </span>
          </a>
          <div style={{ ...link(false), display: "flex", justifyContent: "space-between", cursor: "default" }}>
            <span>{t("sidebar:library.feuillets")}</span>
            <span style={{ color: tokens.inkFaint, fontFamily: tokens.ffMono, fontSize: 11 }}>
              {library?.total_feuillets ?? 0}
            </span>
          </div>
        </div>
      )}

      {/* Account */}
      <p style={sectionHeader}>{t("sidebar:nav_section.account")}</p>
      <nav style={navContainer}>
        <a href={`/projects/${pid}/admin`} style={link(isTabActive("admin"))}>
          {t("sidebar:tabs.settings")}
        </a>
      </nav>
    </div>
  );
};

export default SidebarNav;
