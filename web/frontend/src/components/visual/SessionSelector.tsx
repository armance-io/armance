"use client";

import { type CSSProperties, type FC, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listSessions } from "@/lib/api";
import { useSessionLocked } from "@/lib/sessionBus";
import { useRouteParams } from "@/lib/routeParams";
import { tokens } from "../_shared/armance-tokens";

/**
 * Header session selector (TUI resume parity). Shows the active session;
 * deroulable to load an older one. Becomes read-only (id only) once the user
 * has sent a message in the current session (sessionBus lock).
 */
function shortId(id: string): string {
  return id.length > 12 ? id.slice(0, 12) : id;
}

export const SessionSelector: FC<{ t: (k: string) => string }> = ({ t }) => {
  const { pid, sid } = useRouteParams();
  const locked = useSessionLocked();
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
    fontFamily: tokens.ffMono, fontSize: 11, cursor: locked ? "default" : "pointer",
  };

  const idLabel = `${t("session:selector.id_label")}: ${shortId(sid)}`;

  if (locked) {
    return (
      <span style={{ ...pill, cursor: "default" }} title={t("session:selector.locked_aria")} data-testid="session-selector-locked">
        {idLabel}
      </span>
    );
  }

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
              <span style={{ fontFamily: tokens.ffMono, fontSize: 12 }}>{shortId(s.id)}</span>
              <span style={{ marginLeft: "auto", fontFamily: tokens.ffMono, fontSize: 10, color: tokens.inkFaint }}>
                {t("session:selector.summary").replace("{turns}", String(s.turns)).replace("{tokens}", String(s.est_tokens))}
              </span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
};

export default SessionSelector;
