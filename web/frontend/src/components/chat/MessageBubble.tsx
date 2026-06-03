import { type CSSProperties, type FC, useCallback, useState } from "react";

import { MarkdownRenderer } from "@/components/render/MarkdownRenderer";

/* ─── Types ──────────────────────────────────────────────────────────────── */

export interface MessageBubbleProps {
  role: "user" | "agent";
  agentName: string;
  agentPortraitSrc?: string;
  agentColour: string;
  markdown: string;
  timestamp: string;
  streaming?: boolean;
  t: (key: string) => string;
}

function isSwitchMessage(markdown: string): boolean {
  if (!markdown) return false;
  const lc = markdown.toLowerCase().trim();
  // Check if it starts with OK prefix or is a direct switch confirmation
  const isMatch = [
    "ok — basculé sur",
    "ok - basculé sur",
    "ok — switched to",
    "ok - switched to",
    "basculé sur l'agent",
    "switched to agent",
    "votre interlocuteur",
    "your interlocutor",
    "gesprächspartner",
    "su interlocutor",
    "対話相手",
    "您的对话者",
  ].some(kw => lc.startsWith(kw));
  return isMatch;
}

function formatSwitchMessage(markdown: string, t: (k: string) => string): string {
  if (!markdown) return markdown;
  const lc = markdown.toLowerCase();

  if (["votre interlocuteur", "your interlocutor", "gesprächspartner", "su interlocutor", "対話相手", "您的对话者"].some(kw => lc.includes(kw))) {
    return markdown;
  }

  // Try to parse the name dynamically
  // Supports:
  // "OK - basculé sur Aisha · woodworker. A vous"
  // "OK — basculé sur Aisha. À vous."
  // "OK — switched to Aisha. Go ahead."
  // "OK — switched to Aisha."
  const match = markdown.match(/(?:basculé sur|switched to)\s+([^.·\n]+)/i);
  if (match && match[1]) {
    const name = match[1].trim();
    if (name) {
      return t("chat:agents.switched").replace("{name}", name);
    }
  }

  // Fallback to legacy behavior if regex fails
  const names = ["Malik", "Kim", "Serge", "Mona", "Armance"];
  const matched = names.find(name => markdown.includes(name));
  return matched ? t("chat:agents.switched").replace("{name}", matched) : markdown;
}

/* ─── Component ──────────────────────────────────────────────────────────── */

export const MessageBubble: FC<MessageBubbleProps> = ({
  role,
  agentName,
  agentPortraitSrc,
  agentColour,
  markdown,
  timestamp,
  streaming = false,
  t,
}) => {
  const isAgent = role === "agent";
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    void navigator.clipboard.writeText(markdown).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  }, [markdown]);

  const isSystemSwitch = (agentName === "system" && !markdown.startsWith("⚠")) || (role === "agent" && isSwitchMessage(markdown));
  const displayMarkdown = isSystemSwitch ? formatSwitchMessage(markdown, t) : markdown;

  if (isSystemSwitch) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          width: "100%",
          padding: "16px 24px 16px 16px",
          userSelect: "none",
        }}
      >
        <div style={{ flex: 1, height: "1px", background: "var(--rule, #d6c8ad)", opacity: 0.8 }} />
        <span
          style={{
            padding: "0 16px",
            fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
            fontSize: "12px",
            fontStyle: "italic",
            color: "var(--ink-soft, #5b5145)",
            letterSpacing: "0.03em",
            whiteSpace: "nowrap",
          }}
        >
          {displayMarkdown}
        </span>
        <div style={{ flex: 1, height: "1px", background: "var(--rule, #d6c8ad)", opacity: 0.8 }} />
      </div>
    );
  }

  /* ── Styles ── */
  const wrapStyle: CSSProperties = {
    display: "flex", justifyContent: isAgent ? "flex-start" : "flex-end", padding: "6px 0",
  };

  const outerStyle: CSSProperties = {
    display: "flex", gap: "10px", maxWidth: "72%", minWidth: 0,
    flexDirection: isAgent ? "row" : "row-reverse", alignItems: "flex-start",
  };

  const portraitStyle: CSSProperties = {
    width: "32px", height: "32px", borderRadius: "999px", overflow: "hidden", flexShrink: 0,
    border: "1px solid var(--rule, #d6c8ad)", background: agentColour, display: "flex",
    alignItems: "center", justifyContent: "center", fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontSize: "16px", color: "oklch(0.97 0.012 82)",
  };

  const bubbleStyle: CSSProperties = {
    background: isAgent ? "var(--bg-paper-card, #faf6ef)" : "color-mix(in srgb, var(--accent) 7%, var(--bg-paper-deep, #e8dfcd))",
    border: `1px solid ${isAgent ? `color-mix(in srgb, ${agentColour} 40%, var(--rule, #d6c8ad))` : "var(--rule, #d6c8ad)"}`,
    borderRadius: "6px", padding: "10px 14px", minWidth: W_BUBBLE_MIN,
  };

  const headerStyle: CSSProperties = {
    display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", marginBottom: "6px", width: "100%",
  };

  const bulletStyle: CSSProperties = {
    width: "8px", height: "8px", borderRadius: "999px", background: agentColour, flexShrink: 0,
    animation: streaming ? "msgbubble-pulse 220ms ease-in-out infinite alternate" : "none",
  };

  const nameStyle: CSSProperties = {
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)", fontSize: "11px", fontWeight: 600,
    color: "var(--ink-soft, #5b5145)", letterSpacing: "0.03em", textTransform: "uppercase",
  };

  const proseStyle: CSSProperties = {
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)", fontSize: "12.5px", lineHeight: 1.55, color: "var(--ink, #2a2520)",
  };

  const footerStyle: CSSProperties = {
    display: "flex", justifyContent: "flex-end", marginTop: "4px",
  };

  const timeStyle: CSSProperties = {
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)", fontSize: "8.5px", color: "var(--ink-faint, #9c8e7e)", opacity: 0.7,
  };

  const copyBtnStyle: CSSProperties = {
    display: "flex", alignItems: "center", justifyContent: "center", width: "14px", height: "14px",
    padding: 0, border: "none", borderRadius: "3px", background: "transparent",
    color: copied ? "var(--accent, #6b4f8a)" : "var(--ink-faint, #9c8e7e)",
    cursor: "pointer", transition: "color 0.15s ease, opacity 0.15s ease", flexShrink: 0,
  };

  const formatTimestamp = (ts: string): string => {
    try {
      const d = new Date(ts);
      if (isNaN(d.getTime())) return ts;
      const locale = typeof window !== "undefined" ? window.navigator.language : undefined;
      return d.toLocaleString(locale, {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return ts;
    }
  };

  return (
    <div style={wrapStyle}>
      <style>{`
        @keyframes msgbubble-pulse { 0% { opacity: 1; transform: scale(1); } 100% { opacity: 0.5; transform: scale(0.85); } }
        @keyframes msgbubble-spin { to { transform: rotate(360deg); } }
        .msg-bubble-prose p { margin: 0 0 8px; }
        .msg-bubble-prose p:last-child { margin-bottom: 0; }
        .msg-bubble-prose code { font-family: var(--ff-mono, "JetBrains Mono", monospace); font-size: 0.88em; padding: 1px 5px; border-radius: 3px; background: var(--bg-paper-deep, #e8dfcd); color: var(--accent-deep, #4a3666); }
        .msg-bubble-prose strong { font-weight: 600; }
        .msg-bubble-prose em { font-style: italic; }
        .msg-bubble-prose a { color: var(--accent, #6b4f8a); text-decoration: underline; }
        .msg-bubble-prose ul, .msg-bubble-prose ol { margin: 4px 0 8px; padding-left: 20px; }
        .msg-bubble-prose li { margin: 2px 0; }
        .prose-copy-btn { opacity: 0.5; }
        .prose-copy-btn:hover { background: var(--bg-paper-deep, #e8dfcd) !important; color: var(--accent, #6b4f8a) !important; opacity: 1 !important; }
        @media (prefers-reduced-motion: reduce) { * { animation: none !important; } }
      `}</style>

      <div style={outerStyle}>
        {isAgent && (
          <div style={portraitStyle} aria-hidden="true">
            {agentPortraitSrc ? (
              <img
                src={agentPortraitSrc}
                alt=""
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                }}
              />
            ) : (
              agentName.charAt(0).toUpperCase()
            )}
          </div>
        )}

        <div style={bubbleStyle}>
          <div style={headerStyle}>
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              {isAgent && <span style={bulletStyle} aria-hidden="true" />}
              <span style={nameStyle}>{isAgent ? agentName : (t("chat:you") || "you")}</span>
            </div>
            {markdown && !streaming && (
              <button
                type="button"
                className="prose-copy-btn"
                style={copyBtnStyle}
                onClick={handleCopy}
                aria-label={t("chat:copy.aria")}
                title={copied ? t("chat:copy.done") : t("chat:copy.label")}
              >
                {copied ? (
                  <svg width="10" height="10" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M2.5 7.5l3 3 6-7" />
                  </svg>
                ) : (
                  <svg width="10" height="10" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <rect x="1" y="1" width="8" height="8" rx="1" />
                    <rect x="4" y="4" width="8" height="8" rx="1" fill={isAgent ? "var(--bg-paper-card, #faf6ef)" : "color-mix(in srgb, var(--accent) 7%, var(--bg-paper-deep, #e8dfcd))"} />
                  </svg>
                )}
              </button>
            )}
          </div>

          <div className="msg-bubble-prose" style={proseStyle}>
            <MarkdownRenderer markdown={markdown} t={t} />
          </div>

          <div style={footerStyle}>
            <span style={timeStyle}>{formatTimestamp(timestamp)}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

const W_BUBBLE_MIN = "120px";

export default MessageBubble;
