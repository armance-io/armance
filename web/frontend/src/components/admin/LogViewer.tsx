import { type CSSProperties, type FC, useMemo, useRef, useState, useEffect } from "react";
import { tokens } from "../_shared/armance-tokens";

export interface LogEntry {
  id: string;
  ts: string;
  agent: string;
  level: "debug" | "info" | "warn" | "error";
  message: string;
  payload?: unknown;
}

export interface LogViewerProps {
  entries: LogEntry[];
  agents: string[];
  loadMore?: () => Promise<void>;
  hasMore?: boolean;
  t: (key: string) => string;
}

export const LogViewer: FC<LogViewerProps> = ({
  entries,
  agents,
  loadMore,
  hasMore,
  t,
}) => {
  const [agent, setAgent] = useState<string>("");
  const [from, setFrom] = useState<string>("");
  const [to, setTo] = useState<string>("");
  const [q, setQ] = useState<string>("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const scrollRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(
    () =>
      entries.filter((e) => {
        if (agent && e.agent !== agent) return false;
        if (from && e.ts < from) return false;
        if (to && e.ts > to) return false;
        if (q && !e.message.toLowerCase().includes(q.toLowerCase())) return false;
        return true;
      }),
    [entries, agent, from, to, q],
  );

  useEffect(() => {
    const el = scrollRef.current;
    if (!el || !loadMore || !hasMore) return;
    const onScroll = () => {
      if (el.scrollTop + el.clientHeight >= el.scrollHeight - 200) {
        loadMore();
      }
    };
    el.addEventListener("scroll", onScroll);
    return () => el.removeEventListener("scroll", onScroll);
  }, [loadMore, hasMore]);

  // Live tail: auto-scroll to the bottom when new entries arrive, unless the
  // user has scrolled up to read history (then leave their position alone).
  const atBottomRef = useRef(true);
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const track = () => {
      atBottomRef.current = el.scrollTop + el.clientHeight >= el.scrollHeight - 40;
    };
    el.addEventListener("scroll", track);
    return () => el.removeEventListener("scroll", track);
  }, []);
  useEffect(() => {
    const el = scrollRef.current;
    if (el && atBottomRef.current) el.scrollTop = el.scrollHeight;
  }, [filtered.length]);

  const toggle = (id: string) => {
    setExpanded((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const root: CSSProperties = {
    background: tokens.bgPaperCard,
    border: `1px solid ${tokens.rule}`,
    fontFamily: tokens.ffSans,
    color: tokens.ink,
    display: "flex",
    flexDirection: "column",
    height: "100%",
    minHeight: 0,
  };
  const filterBar: CSSProperties = {
    position: "sticky",
    top: 0,
    display: "flex",
    gap: 10,
    flexWrap: "wrap",
    padding: "12px 16px",
    borderBottom: `1px solid ${tokens.rule}`,
    background: tokens.bgPaperDeep,
    zIndex: 2,
  };
  const inputStyle: CSSProperties = {
    padding: "6px 10px",
    border: `1px solid ${tokens.rule}`,
    background: tokens.bgPaper,
    fontFamily: tokens.ffMono,
    fontSize: 12,
    color: tokens.ink,
  };

  return (
    <div style={root}>
      <div style={filterBar}>
        <select
          value={agent}
          onChange={(e) => setAgent(e.target.value)}
          style={inputStyle}
          aria-label={t("admin:logs.filter.agent")}
        >
          <option value="">{t("admin:logs.filter.all_agents")}</option>
          {agents.map((a) => (
            <option key={a}>{a}</option>
          ))}
        </select>
        <input
          type="datetime-local"
          value={from}
          onChange={(e) => setFrom(e.target.value)}
          style={inputStyle}
          aria-label={t("admin:logs.filter.from")}
        />
        <input
          type="datetime-local"
          value={to}
          onChange={(e) => setTo(e.target.value)}
          style={inputStyle}
          aria-label={t("admin:logs.filter.to")}
        />
        <input
          type="search"
          placeholder={t("admin:logs.filter.search")}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ ...inputStyle, flex: 1, minWidth: 180 }}
        />
      </div>

      <div ref={scrollRef} style={{ flex: 1, minHeight: 0, overflow: "auto" }}>
        {filtered.map((e) => (
          <LogRow
            key={e.id}
            entry={e}
            expanded={expanded.has(e.id)}
            onToggle={() => toggle(e.id)}
          />
        ))}
        {filtered.length === 0 && (
          <div style={{ padding: 40, textAlign: "center", color: tokens.inkFaint }}>
            {t("admin:logs.empty")}
          </div>
        )}
        {hasMore && (
          <div style={{ padding: 16, textAlign: "center", color: tokens.inkFaint, fontSize: 12 }}>
            {t("admin:logs.loading_more")}
          </div>
        )}
      </div>
    </div>
  );
};

const LEVEL_COLORS: Record<LogEntry["level"], string> = {
  debug: "#8a8273",
  info: "#5b5145",
  warn: "#b08a3a",
  error: "#a44141",
};

const LogRow: FC<{ entry: LogEntry; expanded: boolean; onToggle: () => void }> = ({
  entry,
  expanded,
  onToggle,
}) => (
  <div style={{ borderBottom: `1px solid ${tokens.rule}` }}>
    <button
      type="button"
      onClick={onToggle}
      style={{
        display: "grid",
        gridTemplateColumns: "auto 60px 110px 1fr",
        gap: 12,
        alignItems: "center",
        width: "100%",
        padding: "8px 16px",
        background: "transparent",
        border: "none",
        textAlign: "left",
        cursor: "pointer",
        fontFamily: tokens.ffMono,
        fontSize: 12,
        color: tokens.ink,
      }}
    >
      <span style={{ color: tokens.inkFaint }}>{expanded ? "▾" : "▸"}</span>
      <span
        style={{
          color: LEVEL_COLORS[entry.level],
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          fontSize: 11,
        }}
      >
        {entry.level}
      </span>
      <span style={{ color: tokens.inkSoft }}>{entry.ts.replace("T", " ").slice(0, 19)}</span>
      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        <span style={{ color: tokens.accent, marginRight: 8 }}>{entry.agent}</span>
        {entry.message}
      </span>
    </button>
    {expanded && entry.payload !== undefined && (
      <pre
        style={{
          margin: 0,
          padding: "12px 16px 16px 48px",
          fontFamily: tokens.ffMono,
          fontSize: 12,
          color: tokens.inkSoft,
          background: tokens.bgPaperDeep,
          overflow: "auto",
        }}
      >
        {JSON.stringify(entry.payload, null, 2)}
      </pre>
    )}
  </div>
);

export default LogViewer;
