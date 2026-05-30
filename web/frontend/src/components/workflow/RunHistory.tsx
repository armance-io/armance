import {
  type CSSProperties,
  type FC,
  useState,
  useCallback,
} from "react";
import { DeleteRunButton } from "./DeleteRunButton";

/* ─── Types ──────────────────────────────────────────────────────────────── */

type RunStatus = "running" | "completed" | "failed" | "cancelled";

interface RunItem {
  run_id: string;
  status: RunStatus;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  tokens_total: number | null;
}

export interface RunHistoryProps {
  runs: RunItem[];
  onOpen: (runId: string) => void;
  onDelete: (runId: string) => Promise<void>;
  t: (key: string) => string;
}

/* ─── Helpers ────────────────────────────────────────────────────────────── */

const STATUS_COLORS: Record<RunStatus, { bg: string; border: string; pulse?: boolean }> = {
  running: { bg: "hsl(35, 30%, 60%)", border: "hsl(35, 30%, 50%)", pulse: true },
  completed: { bg: "hsl(120, 15%, 55%)", border: "hsl(120, 15%, 45%)" },
  failed: { bg: "hsl(0, 30%, 65%)", border: "hsl(0, 30%, 55%)" },
  cancelled: { bg: "var(--ink-faint, #9c8e7e)", border: "rgba(42, 37, 32, 0.2)" },
};

function formatDuration(ms: number | null): string {
  if (ms === null || ms === undefined || ms < 0) return "--:--";
  const totalSec = Math.floor(ms / 1000);
  const hrs = Math.floor(totalSec / 3600);
  const mins = Math.floor((totalSec % 3600) / 60);
  const secs = totalSec % 60;
  if (hrs > 0) {
    return `${String(hrs).padStart(2, "0")}:${String(mins).padStart(2, "0")}`;
  }
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function formatTokens(tokens: number | null): string {
  if (tokens === null || tokens === undefined || tokens < 0) return "--";
  if (tokens < 1000) return String(tokens);
  const k = tokens / 1000;
  return `${k.toFixed(1)}k`;
}

function formatTimeAgo(startedAt: string, t: (key: string) => string): string {
  try {
    const diff = Date.now() - new Date(startedAt).getTime();
    const mins = Math.floor(diff / 60_000);
    if (mins < 1) return t("workflow:history.time_just_now");
    if (mins < 60) {
      return t("workflow:history.time_mins")
        .replace("{count}", String(mins))
        .replace("{{count}}", String(mins));
    }
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) {
      return t("workflow:history.time_hours")
        .replace("{count}", String(hrs))
        .replace("{{count}}", String(hrs));
    }
    const days = Math.floor(hrs / 24);
    return t("workflow:history.time_days")
      .replace("{count}", String(days))
      .replace("{{count}}", String(days));
  } catch {
    return startedAt;
  }
}

/* ─── Component ──────────────────────────────────────────────────────────── */

export const RunHistory: FC<RunHistoryProps> = ({
  runs,
  onOpen,
  onDelete,
  t,
}) => {
  const [isOpen, setIsOpen] = useState(true);

  const toggleOpen = useCallback(() => {
    setIsOpen((prev) => !prev);
  }, []);

  /* ─── Styles ───────────────────────────────────────────────────────────── */

  const containerStyle: CSSProperties = {
    display: "flex",
    flexDirection: "column",
    width: "100%",
  };

  const headerStyle: CSSProperties = {
    height: "32px",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 8px",
    cursor: "pointer",
    userSelect: "none",
    background: "transparent",
    border: "none",
    width: "100%",
    outline: "none",
  };

  const headerTitleStyle: CSSProperties = {
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "13px",
    fontWeight: 500,
    color: "var(--ink-soft, #5b5145)",
    display: "flex",
    alignItems: "center",
    gap: "6px",
  };

  const listStyle: CSSProperties = {
    display: isOpen ? "flex" : "none",
    flexDirection: "column",
    width: "100%",
    paddingLeft: "8px",
  };

  const rowStyle: CSSProperties = {
    height: "32px",
    display: "flex",
    alignItems: "center",
    gap: "8px",
    padding: "0 8px",
    cursor: "pointer",
    borderRadius: "2px",
    outline: "none",
  };

  const timeStyle: CSSProperties = {
    flex: 1,
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "12px",
    color: "var(--ink-soft, #5b5145)",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  };

  const durationStyle: CSSProperties = {
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "11px",
    color: "var(--ink-soft, #5b5145)",
  };

  const tokensStyle: CSSProperties = {
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "11px",
    color: "var(--ink-soft, #5b5145)",
    minWidth: "36px",
    textAlign: "right",
  };

  const emptyStyle: CSSProperties = {
    height: "36px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "8px",
  };

  const fleurStyle: CSSProperties = {
    fontSize: "14px",
    color: "var(--accent-soft, #b7a4c9)",
    userSelect: "none",
  };

  const emptyTextStyle: CSSProperties = {
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontStyle: "italic",
    fontSize: "12px",
    color: "var(--ink-soft, #5b5145)",
  };

  return (
    <div style={containerStyle}>
      <style>{`
        .run-row:hover,
        .run-row:focus {
          background: var(--bg-paper-deep, #e8dfcd) !important;
          outline: none;
        }
        @keyframes runhistory-pulse {
          0% { opacity: 1; transform: scale(1); }
          100% { opacity: 0.45; transform: scale(0.85); }
        }
        @media (prefers-reduced-motion: reduce) {
          * {
            transition: none !important;
            animation: none !important;
          }
        }
      `}</style>

      <button
        style={headerStyle}
        onClick={toggleOpen}
        aria-expanded={isOpen}
        aria-label={`${t("workflow:history.title")} (${runs.length} runs)`}
      >
        <span style={headerTitleStyle}>
          <span>{t("workflow:history.title")}</span>
          <span style={{ opacity: 0.75 }}>·</span>
          <span>{runs.length}</span>
        </span>
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="var(--ink-soft, #5b5145)"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{
            transform: isOpen ? "rotate(90deg)" : "rotate(0deg)",
            transition: "transform 120ms ease",
          }}
          aria-hidden="true"
        >
          <polyline points="9 18 15 12 9 6" />
        </svg>
      </button>

      <div id="run-history-list" style={listStyle}>
        {runs.length === 0 ? (
          <div style={emptyStyle}>
            <span style={fleurStyle} aria-hidden="true">
              ❦
            </span>
            <span style={emptyTextStyle}>{t("workflow:history.empty")}</span>
          </div>
        ) : (
          runs.map((run) => (
            <div
              key={run.run_id}
              className="run-row"
              style={rowStyle}
              onClick={() => onOpen(run.run_id)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onOpen(run.run_id);
                }
              }}
              aria-label={`${t(`workflow:history.status.${run.status}`)} run ${run.run_id}`}
            >
              <span
                style={{
                  display: "inline-block",
                  width: "10px",
                  height: "10px",
                  borderRadius: "50%",
                  backgroundColor: STATUS_COLORS[run.status].bg,
                  border: `1px solid ${STATUS_COLORS[run.status].border}`,
                  flexShrink: 0,
                  animation: STATUS_COLORS[run.status].pulse ? "runhistory-pulse 1s infinite alternate" : "none",
                }}
                title={t(`workflow:history.status.${run.status}`)}
                aria-hidden="true"
              />

              <span
                style={timeStyle}
                title={new Date(run.started_at).toLocaleString()}
              >
                {formatTimeAgo(run.started_at, t)}
              </span>

              <span
                style={durationStyle}
                aria-label={`${t("workflow:history.duration_aria")} ${formatDuration(run.duration_ms)}`}
              >
                {formatDuration(run.duration_ms)}
              </span>

              <span style={tokensStyle} aria-label={`${formatTokens(run.tokens_total)} tokens`}>
                {formatTokens(run.tokens_total)}
              </span>

              <div
                style={{ flexShrink: 0, display: "flex", alignItems: "center" }}
                onClick={(e) => e.stopPropagation()}
              >
                <DeleteRunButton
                  runId={run.run_id}
                  status={run.status}
                  onDelete={onDelete}
                  t={t}
                />
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default RunHistory;
