import {
  type CSSProperties,
  type FC,
  type ReactNode,
  useEffect,
  useRef,
  useState,
} from "react";

import { ThemeToggle } from "./ThemeToggle";
import { SidebarNav } from "./SidebarNav";
import { HeaderMetrics } from "./HeaderMetrics";
import { HeaderModel } from "./HeaderModel";
import { SessionSelector } from "./SessionSelector";

/* ─── Types ──────────────────────────────────────────────────────────────── */

export interface AppShellProps {
  /** Content rendered inside the collapsible left sidebar. */
  sidebar?: ReactNode;
  /** Page body — fills the main content area. */
  children: ReactNode;
  /**
   * i18n accessor.
   * Keys: visual:shell.brand_domain · sidebar_collapse_aria ·
   *       footer_motto · footer_line · visual:theme.toggle_aria
   */
  t: (key: string) => string;
}

/* ─── Constants ──────────────────────────────────────────────────────────── */

const KEY_COLLAPSED = "armance.sidebar-collapsed";
const KEY_WIDTH     = "armance.sidebar-width";
const HEADER_H      = 56;
const W_DEFAULT     = 280;
const W_MIN         = 160;
const W_MAX         = 520;

/* ─── ChevronIcon ────────────────────────────────────────────────────────── */

const ChevronIcon: FC<{ collapsed: boolean }> = ({ collapsed }) => (
  <svg
    width="16" height="16" viewBox="0 0 16 16"
    fill="none" stroke="currentColor"
    strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
    aria-hidden="true"
  >
    {collapsed
      ? <path d="M6 12l4-4-4-4" />   /* › */
      : <path d="M10 12L6 8l4-4" />  /* ‹ */
    }
  </svg>
);

/* ─── AppShell ───────────────────────────────────────────────────────────── */

/**
 * `<AppShell />` — top-level authenticated layout.
 *
 * - Header (56 px, sticky) with brand + theme toggle.
 * - Sidebar: collapses fully to 0 px; horizontally resizable via drag handle;
 *   both states persisted to localStorage.
 * - Main: scrollable content area.
 * - Footer: centred fleuron + copy lines.
 */
export const AppShell: FC<AppShellProps> = ({ sidebar, children, t }) => {
  const [collapsed,   setCollapsed]   = useState(false);
  const [sidebarW,    setSidebarW]    = useState(W_DEFAULT);
  const [handleHover, setHandleHover] = useState(false);
  const [dragging,    setDragging]    = useState(false);
  const [toggleHover, setToggleHover] = useState(false);


  const motion = useRef(
    typeof window !== "undefined"
      ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
      : false,
  ).current;

  /* ── Mount: restore persisted state ── */
  useEffect(() => {
    if (localStorage.getItem(KEY_COLLAPSED) === "true") setCollapsed(true);
    const stored = parseInt(localStorage.getItem(KEY_WIDTH) ?? "", 10);
    if (!isNaN(stored) && stored >= W_MIN && stored <= W_MAX) setSidebarW(stored);
  }, []);

  /* ── Toggle ── */
  function toggleSidebar(): void {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem(KEY_COLLAPSED, String(next));
      return next;
    });
  }

  /* ── Drag-to-resize ── */
  function onDragStart(e: React.MouseEvent): void {
    e.preventDefault();
    const startX = e.clientX;
    const startW = sidebarW;
    setDragging(true);
    document.body.style.cursor     = "col-resize";
    document.body.style.userSelect = "none";

    function onMove(ev: MouseEvent): void {
      setSidebarW(Math.max(W_MIN, Math.min(W_MAX, startW + ev.clientX - startX)));
    }
    function onUp(): void {
      setDragging(false);
      document.body.style.cursor     = "";
      document.body.style.userSelect = "";
      setSidebarW((w) => { localStorage.setItem(KEY_WIDTH, String(w)); return w; });
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup",   onUp);
    }
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup",   onUp);
  }

  /* ── Styles ── */
  const actualW = collapsed ? 0 : sidebarW;
  const ease    = "cubic-bezier(0.4,0,0.2,1)";

  // height (not minHeight): bound the column to the viewport so the chat
  // scroll area is constrained and scrolls, instead of growing forever.
  const shellStyle: CSSProperties = {
    display: "flex", flexDirection: "column",
    height: "100vh",
    background: "var(--bg-paper,#f4ede0)",
  };

  const headerStyle: CSSProperties = {
    height: `${HEADER_H}px`, flexShrink: 0,
    display: "flex", alignItems: "center", paddingRight: "20px",
    background: "var(--bg-paper-deep,#e8dfcd)",
    borderBottom: "1px solid var(--rule,#d6c8ad)",
    position: "sticky", top: 0, zIndex: 50,
  };

  // BUG-07: no border, same background as the header; the only separation is
  // a thin vertical rule on the right. A subtle ink shift signals hover.
  const toggleStyle: CSSProperties = {
    width: `${HEADER_H}px`, height: `${HEADER_H}px`,
    flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center",
    color: toggleHover ? "var(--ink,#2a2520)" : "var(--ink-soft,#5b5145)",
    border: "none",
    borderRight: "1px solid var(--rule,#d6c8ad)",
    transition: motion ? "none" : "color 0.15s ease",
    padding: 0,
    background: "var(--bg-paper-deep,#e8dfcd)",
    cursor: "pointer",
    outline: "none",
  };

  const sidebarStyle: CSSProperties = {
    width: `${actualW}px`, flexShrink: 0,
    background: "var(--bg-paper,#f4ede0)",
    overflowY: "auto", overflowX: "hidden",
    borderRight: actualW > 0 ? "1px solid var(--rule,#d6c8ad)" : "none",
    transition: motion || dragging ? "none" : `width 0.25s ${ease}, border-color 0.25s ${ease}`,
  };

  const sidebarInnerStyle: CSSProperties = {
    width: `${sidebarW}px`,
    opacity: collapsed ? 0 : 1,
    pointerEvents: collapsed ? "none" : undefined,
    transition: motion ? "none" : "opacity 0.15s ease",
  };

  const handleStyle: CSSProperties = {
    width: "5px", flexShrink: 0,
    cursor: "col-resize",
    background: handleHover || dragging
      ? "var(--accent-soft,#b7a4c9)"
      : "var(--rule,#d6c8ad)",
    transition: motion ? "none" : "background 0.15s ease",
    marginLeft: "-1px", zIndex: 1,
  };

  // No padding here — each page owns its content rhythm (TabContent / the
  // admin outer / full-bleed chat) so every surface starts at the same offset.
  const mainStyle: CSSProperties = {
    flex: 1, overflowY: "auto",
    background: "var(--bg-paper-deep,#e8dfcd)",
  };

  // BUG-09: compact footer — one line, minimal vertical padding.
  const footerStyle: CSSProperties = {
    borderTop: "1px solid var(--rule,#d6c8ad)",
    padding: "8px 24px",
    background: "var(--bg-paper-deep,#e8dfcd)",
    display: "flex",
    alignItems: "center", justifyContent: "center", gap: "10px",
  };

  const inlineSerif  = { fontFamily: "var(--ff-serif,'Instrument Serif',serif)" } as const;
  const inlineMono   = { fontFamily: "var(--ff-mono,monospace)" } as const;

  return (
    <div style={shellStyle}>

      <header style={headerStyle}>
        <button type="button" style={toggleStyle}
          onClick={toggleSidebar}
          onMouseEnter={() => setToggleHover(true)}
          onMouseLeave={() => setToggleHover(false)}
          aria-label={t("visual:shell.sidebar_collapse_aria")}
          aria-expanded={!collapsed}
        >
          <ChevronIcon collapsed={collapsed} />
        </button>

        <div style={{ display: "flex", alignItems: "baseline", marginLeft: "20px" }}>
          <span style={{ ...inlineSerif, fontStyle: "italic", fontSize: "18px", color: "var(--ink,#2a2520)" }}>Armance</span>
          <span style={{ color: "var(--rule,#d6c8ad)", margin: "0 8px" }}>·</span>
          <a
            href="https://armance.io"
            target="_blank"
            rel="noopener noreferrer"
            style={{ ...inlineMono, fontSize: "10px", letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--ink-faint,#9c8e7e)", textDecoration: "none" }}
          >
            {t("visual:shell.brand_domain")}
          </a>
        </div>

        {/* Centred session selector (TUI resume parity). */}
        <div style={{ position: "absolute", left: "50%", transform: "translateX(-50%)" }}>
          <SessionSelector t={t} />
        </div>

        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "16px" }}>
          <HeaderModel t={t} />
          <HeaderMetrics t={t} />
          <ThemeToggle t={t} />
        </div>
      </header>

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <aside style={sidebarStyle} aria-hidden={collapsed}>
          <div style={sidebarInnerStyle}>
            <SidebarNav t={t} />
            {sidebar && (
              <>
                <div style={{ borderTop: "1px solid var(--rule, #d6c8ad)", margin: "12px 12px 0" }} />
                {sidebar}
              </>
            )}
          </div>
        </aside>

        {!collapsed && (
          <div
            style={handleStyle}
            onMouseDown={onDragStart}
            onMouseEnter={() => setHandleHover(true)}
            onMouseLeave={() => setHandleHover(false)}
            aria-hidden="true"
          />
        )}

        <main style={mainStyle}>{children}</main>
      </div>

      <footer style={footerStyle}>
        <span style={{ ...inlineSerif, fontSize: "13px", color: "var(--accent,#6b4f8a)", lineHeight: 1 }} aria-hidden="true">❦</span>
        <span style={{ fontFamily: "var(--ff-sans,sans-serif)", fontSize: "12px", color: "var(--ink-soft,#5b5145)" }}>
          {t("visual:shell.footer_motto")}
        </span>
        <span style={{ color: "var(--rule,#d6c8ad)" }} aria-hidden="true"> · </span>
        <a
          href="https://armance.io"
          target="_blank"
          rel="noopener noreferrer"
          style={{ ...inlineMono, fontSize: "10px", letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--ink-faint,#9c8e7e)", textDecoration: "none" }}
        >
          armance.io
        </a>
        <span style={{ color: "var(--rule,#d6c8ad)" }} aria-hidden="true"> · </span>
        <span style={{ ...inlineMono, fontSize: "10px", letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--ink-faint,#9c8e7e)" }}>
          {t("visual:shell.footer_line")}
        </span>
      </footer>

    </div>
  );
};

export default AppShell;
