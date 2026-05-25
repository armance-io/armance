import {
  type CSSProperties,
  type FC,
  type ReactNode,
  useState,
  useRef,
  useCallback,
  useEffect,
} from "react";

/* ─── Types ──────────────────────────────────────────────────────────────── */

interface Agent {
  name: string;
  role: string;
  provider: string;
  model: string;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number | null;
  persona: string;
  portraitSrc?: string;
  colour: string;
}

export interface AgentTooltipProps {
  agent: Agent;
  children: ReactNode;
  t: (key: string) => string;
}

/* ─── Helpers ────────────────────────────────────────────────────────────── */

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

/* ─── Component ──────────────────────────────────────────────────────────── */

export const AgentTooltip: FC<AgentTooltipProps> = ({
  agent,
  children,
  t,
}) => {
  const [visible, setVisible] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const triggerRef = useRef<HTMLSpanElement>(null);

  const show = useCallback(() => {
    timerRef.current = setTimeout(() => setVisible(true), 300);
  }, []);

  const hide = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setVisible(false);
  }, []);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  /* ── Styles ── */

  const triggerStyle: CSSProperties = {
    position: "relative",
    display: "inline-flex",
    cursor: "default",
  };

  const tooltipStyle: CSSProperties = {
    position: "absolute",
    bottom: "calc(100% + 8px)",
    left: "50%",
    transform: "translateX(-50%)",
    width: "280px",
    background: "var(--bg-paper, #f4ede0)",
    border: "1px solid var(--rule, #d6c8ad)",
    boxShadow:
      "0 8px 24px -10px rgba(42,37,32,0.18), 0 2px 6px -2px rgba(42,37,32,0.10)",
    padding: "14px",
    zIndex: 100,
    opacity: visible ? 1 : 0,
    pointerEvents: visible ? "auto" : "none",
    transition: "opacity 160ms ease",
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  };

  const topRowStyle: CSSProperties = {
    display: "flex",
    gap: "10px",
    alignItems: "center",
  };

  const portraitStyle: CSSProperties = {
    width: "36px",
    height: "36px",
    borderRadius: "999px",
    overflow: "hidden",
    flexShrink: 0,
    border: "1px solid var(--rule, #d6c8ad)",
    background: agent.colour,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontSize: "18px",
    color: "oklch(0.97 0.012 82)",
  };

  const nameStyle: CSSProperties = {
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontSize: "16px",
    color: "var(--ink, #2a2520)",
  };

  const roleStyle: CSSProperties = {
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "10px",
    letterSpacing: "0.10em",
    textTransform: "uppercase",
    color: "var(--ink-faint, #9c8e7e)",
  };

  const modelStyle: CSSProperties = {
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "11px",
    color: "var(--ink-soft, #5b5145)",
    letterSpacing: "0.04em",
  };

  const metaRowStyle: CSSProperties = {
    display: "flex",
    gap: "12px",
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "11px",
    color: "var(--ink-soft, #5b5145)",
  };

  const personaStyle: CSSProperties = {
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontStyle: "italic",
    fontSize: "13px",
    lineHeight: 1.45,
    color: "var(--ink-soft, #5b5145)",
    display: "-webkit-box",
    WebkitLineClamp: 3,
    WebkitBoxOrient: "vertical",
    overflow: "hidden",
  };

  return (
    <span
      ref={triggerRef}
      style={triggerStyle}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      <div style={tooltipStyle} role="tooltip" aria-hidden={!visible}>
        <div style={topRowStyle}>
          <div style={portraitStyle} aria-hidden="true">
            {agent.portraitSrc ? (
              <img
                src={agent.portraitSrc}
                alt=""
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                }}
              />
            ) : (
              agent.name.charAt(0).toUpperCase()
            )}
          </div>
          <div>
            <div style={nameStyle}>{agent.name}</div>
            <div style={roleStyle}>{agent.role}</div>
          </div>
        </div>

        <div style={modelStyle}>
          {agent.provider} · {agent.model}
        </div>

        <div style={metaRowStyle}>
          <span>
            {t("chat:tooltip.tokens_in")}: {fmtTokens(agent.tokens_in)}
          </span>
          <span>
            {t("chat:tooltip.tokens_out")}:{" "}
            {fmtTokens(agent.tokens_out)}
          </span>
        </div>
        <div style={metaRowStyle}>
          <span>
            {agent.cost_usd !== null
              ? `${t("chat:tooltip.cost")}: $${agent.cost_usd.toFixed(4)}`
              : t("chat:tooltip.cost_na")}
          </span>
        </div>

        <div style={personaStyle}>{agent.persona}</div>
      </div>
    </span>
  );
};

export default AgentTooltip;
