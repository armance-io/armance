"use client";

import { type CSSProperties, type FC } from "react";
import { useLatestSession } from "@/lib/useLatestSession";

export interface SidebarNavProps {
  t: (key: string) => string;
}

export const SidebarNav: FC<SidebarNavProps> = ({ t }) => {
  const { pid, sid } = useLatestSession();

  const pathname = typeof window !== "undefined" ? window.location.pathname : "";

  // Helper to check if a navigation item is active
  const isTabActive = (tab: string): boolean => {
    if (tab === "workflows") return pathname.includes("/workflows");
    if (tab === "library") return pathname.includes("/library");
    if (tab === "deliverables") return pathname.includes("/deliverables");
    if (tab === "admin") return pathname.includes("/admin");
    return false;
  };

  /* ── Styles ── */
  const sectionHeaderStyle: CSSProperties = {
    fontFamily: "var(--ff-mono, monospace)",
    fontSize: "9px",
    letterSpacing: "0.14em",
    textTransform: "uppercase",
    color: "var(--ink-faint, #9c8e7e)",
    padding: "16px 20px 6px",
    fontWeight: 600,
    userSelect: "none",
  };

  const navContainerStyle: CSSProperties = {
    display: "flex",
    flexDirection: "column",
    gap: "2px",
    padding: "0 12px",
  };

  const linkStyle = (active: boolean): CSSProperties => ({
    display: "block",
    padding: "8px 12px",
    borderRadius: "2px",
    fontSize: "13px",
    fontFamily: "var(--ff-sans, sans-serif)",
    color: active ? "var(--accent, #6b4f8a)" : "var(--ink-soft, #5b5145)",
    background: active ? "color-mix(in srgb, var(--accent, #6b4f8a) 8%, transparent)" : "transparent",
    textDecoration: "none",
    fontWeight: active ? 500 : 400,
    transition: "background 120ms ease, color 120ms ease",
    cursor: "pointer",
  });

  const getWorkflowLink = () => {
    return `/projects/${pid}/sessions/${sid || "_"}/workflows/session_decision`;
  };

  const getLibraryLink = () => {
    return `/projects/${pid}/sessions/${sid || "_"}/library`;
  };

  const getDeliverablesLink = () => {
    return `/projects/${pid}/sessions/${sid || "_"}/deliverables`;
  };

  const getAdminLink = () => {
    return `/projects/${pid}/admin`;
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", width: "100%" }}>
      <p style={sectionHeaderStyle}>{t("sidebar:nav_section.workspace")}</p>
      <nav style={navContainerStyle}>
        <a
          href={sid ? getWorkflowLink() : "#"}
          style={linkStyle(isTabActive("workflows"))}
          onClick={(e) => {
            if (!sid) e.preventDefault();
          }}
        >
          {t("sidebar:tabs.session_active")}
        </a>
        <a
          href={sid ? getLibraryLink() : "#"}
          style={linkStyle(isTabActive("library"))}
          onClick={(e) => {
            if (!sid) e.preventDefault();
          }}
        >
          {t("sidebar:tabs.library")}
        </a>
        <a
          href={sid ? getDeliverablesLink() : "#"}
          style={linkStyle(isTabActive("deliverables"))}
          onClick={(e) => {
            if (!sid) e.preventDefault();
          }}
        >
          {t("sidebar:tabs.deliverables")}
        </a>
      </nav>

      <p style={sectionHeaderStyle}>{t("sidebar:nav_section.account")}</p>
      <nav style={navContainerStyle}>
        <a href={getAdminLink()} style={linkStyle(isTabActive("admin"))}>
          {t("sidebar:tabs.settings")}
        </a>
      </nav>
    </div>
  );
};

export default SidebarNav;
