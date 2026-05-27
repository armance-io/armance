import { type CSSProperties, type FC, useMemo } from "react";

/* ─── Types ──────────────────────────────────────────────────────────────── */

type RunStatus = "running" | "completed" | "failed" | "cancelled";

export interface RunNodeProps {
  run_id: string;
  started_at: string;
  status: RunStatus;
  onClick: () => void;
  t: (key: string) => string;
}

/* ─── Helpers ────────────────────────────────────────────────────────────── */

function timeAgo(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60_000);
    if (mins < 1) return "< 1 min";
    if (mins < 60) return `${mins} min`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h`;
    const days = Math.floor(hrs / 24);
    return `${days}j`;
  } catch {
    return iso;
  }
}

const STATUS_DOT: Record<RunStatus, string> = {
  running: "var(--accent, #6b4f8a)",
  completed: "var(--accent-deep, #4a3666)",
  failed: "oklch(0.55 0.18 25)",
  cancelled: "var(--ink-soft, #5b5145)",
};

/* ─── Component ──────────────────────────────────────────────────────────── */

export const RunNode: FC<RunNodeProps> = ({
  run_id,
  started_at,
  status,
  onClick,
  t,
}) => {
  const ago = useMemo(() => timeAgo(started_at), [started_at]);
  const isRunning = status === "running";

  const boxStyle: CSSProperties = {
    width: "220px",
    height: "60px",
    border: "1px solid var(--accent, #6b4f8a)",
    background: "var(--bg-paper, #f4ede0)",
    padding: "10px 14px",
    display: "flex",
    alignItems: "center",
    gap: "10px",
    cursor: "pointer",
    borderRadius: "2px",
    transition: "background 120ms ease",
  };

  const dotStyle: CSSProperties = {
    width: "8px",
    height: "8px",
    borderRadius: "999px",
    background: STATUS_DOT[status],
    flexShrink: 0,
    animation: isRunning
      ? "runnode-pulse 1.4s ease-in-out infinite"
      : "none",
  };

  const contentStyle: CSSProperties = {
    flex: 1,
    minWidth: 0,
    display: "flex",
    flexDirection: "column",
    gap: "2px",
  };

  const labelStyle: CSSProperties = {
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "13px",
    color: "var(--ink, #2a2520)",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  };

  const statusStyle: CSSProperties = {
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "10px",
    color: "var(--ink-faint, #9c8e7e)",
    letterSpacing: "0.06em",
  };

  return (
    <div
      style={boxStyle}
      onClick={onClick}
      role="button"
      tabIndex={0}
      aria-label={`${t("workflow:run.label")} ${run_id}`}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background =
          "var(--bg-paper-deep, #e8dfcd)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background =
          "var(--bg-paper, #f4ede0)";
      }}
    >
      <style>{`
        @keyframes runnode-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
        @media (prefers-reduced-motion: reduce) {
          * { animation: none !important; transition: none !important; }
        }
      `}</style>

      <span style={dotStyle} aria-hidden="true" />

      <div style={contentStyle}>
        <span style={labelStyle}>
          {t("workflow:run.label")} · {ago}
        </span>
        <span style={statusStyle}>
          {t(`workflow:run.status.${status}`)}
        </span>
      </div>
    </div>
  );
};

export default RunNode;
