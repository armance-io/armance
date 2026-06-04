"use client";

import { type CSSProperties, type FC, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listSessions, createSession } from "@/lib/api";
import { useRouteParams } from "@/lib/routeParams";
import { tokens } from "../_shared/armance-tokens";

/**
 * Header session selector (TUI resume parity). Shows the active session;
 * deroulable to load an older one. Becomes read-only (id only) once the user
 * has sent a message in the current session (sessionBus lock).
 */
function formatSessionId(id: string): string {
  if (id.includes("-")) return id;
  return id.length > 12 ? id.slice(0, 12) : id;
}

export const SessionSelector: FC<{ t: (k: string) => string }> = ({ t }) => {
  const { pid, sid } = useRouteParams();
  const [open, setOpen] = useState(false);

  const { data: sessions = [] } = useQuery({
    queryKey: ["sessions-list", pid],
    enabled: Boolean(pid) && open,
    queryFn: () => listSessions(pid).catch(() => []),
  });

  if (!sid || sid === "_") return null;

  const pill: CSSProperties = {
    display: "inline-flex", alignItems: "center", gap: 6,
    height: "28px", padding: "0 12px",
    border: `1px solid ${tokens.rule}`, borderRadius: tokens.radiusSm,
    background: tokens.bgPaperCard, color: tokens.inkSoft,
    fontFamily: tokens.ffMono, fontSize: 11, cursor: "pointer",
  };

  const idLabel = `${t("session:selector.id_label")}: ${formatSessionId(sid)}`;

  return (
    <div style={{ position: "relative" }} data-testid="session-selector">
      <button type="button" style={pill} onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {idLabel}
        <span aria-hidden="true">{open ? "▴" : "▾"}</span>
      </button>
      {open && (
        <div
          style={{
            position: "absolute", top: "34px", left: "50%", transform: "translateX(-50%)",
            minWidth: 320, maxHeight: 360, overflowY: "auto",
            background: tokens.bgPaperCard, border: `1px solid ${tokens.rule}`,
            borderRadius: tokens.radiusMd, boxShadow: tokens.shadowPop, zIndex: 60, padding: 6,
          }}
        >
          <button
            type="button"
            onClick={async () => {
              try {
                const newSession = await createSession(pid);
                window.location.href = `/projects/${pid}/sessions/${newSession.id}`;
              } catch (err) {
                console.error("Failed to create new session:", err);
              }
            }}
            style={{
              display: "flex", alignItems: "center", gap: 8, padding: "8px 10px",
              width: "100%", border: "none", background: "transparent",
              borderRadius: tokens.radiusSm, cursor: "pointer",
              color: tokens.accent, fontWeight: 600, textAlign: "left",
              fontFamily: tokens.ffSans, fontSize: 12,
              borderBottom: `1px solid ${tokens.ruleSoft || "rgba(0,0,0,0.05)"}`,
              marginBottom: 4,
            }}
          >
            <span style={{ fontSize: 14 }}>+</span>
            <span>{t("visual:empty.session.cta")}</span>
          </button>

          <div style={{ padding: "6px 10px", fontFamily: tokens.ffMono, fontSize: 9, letterSpacing: "0.12em", textTransform: "uppercase", color: tokens.inkFaint }}>
            {t("session:selector.title")}
          </div>
          {sessions.length === 0 && (
            <div style={{ padding: "8px 10px", fontSize: 12, color: tokens.inkFaint, fontStyle: "italic" }}>
              {t("session:selector.empty")}
            </div>
          )}
          {sessions.map((s, i) => (
            <a
              key={s.id}
              href={`/projects/${pid}/sessions/${s.id}`}
              style={{
                display: "flex", alignItems: "baseline", gap: 8, padding: "8px 10px",
                borderRadius: tokens.radiusSm, textDecoration: "none",
                background: s.id === sid ? "color-mix(in srgb, var(--accent) 8%, transparent)" : "transparent",
                color: s.id === sid ? tokens.accent : tokens.ink,
              }}
            >
              <span style={{ fontFamily: tokens.ffMono, fontSize: 10, color: tokens.inkFaint, width: 18 }}>{i + 1}</span>
              <span style={{ fontFamily: tokens.ffMono, fontSize: 12 }}>{formatSessionId(s.id)}</span>
              <span style={{ marginLeft: "auto", fontFamily: tokens.ffMono, fontSize: 10, color: tokens.inkFaint }}>
                {(() => {
                  const ts = s.updated_at || s.created_at;
                  if (!ts) return "";
                  try {
                    const d = new Date(ts);
                    if (isNaN(d.getTime())) return "";
                    const pad = (n: number) => String(n).padStart(2, "0");
                    return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}·${pad(d.getHours())}:${pad(d.getMinutes())}`;
                  } catch {
                    return "";
                  }
                })()}
              </span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
};

export default SessionSelector;
