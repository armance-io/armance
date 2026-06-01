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

  /* ── Styles ── */

  const wrapStyle: CSSProperties = {
    display: "flex",
    justifyContent: isAgent ? "flex-start" : "flex-end",
    padding: "6px 0",
  };

  const outerStyle: CSSProperties = {
    display: "flex",
    gap: "10px",
    maxWidth: "72%",
    minWidth: 0,
    flexDirection: isAgent ? "row" : "row-reverse",
    alignItems: "flex-start",
  };

  const portraitStyle: CSSProperties = {
    width: "32px",
    height: "32px",
    borderRadius: "999px",
    overflow: "hidden",
    flexShrink: 0,
    border: "1px solid var(--rule, #d6c8ad)",
    background: agentColour,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontSize: "16px",
    color: "oklch(0.97 0.012 82)",
  };

  const bubbleStyle: CSSProperties = {
    // User bubbles sit on a darker paper for clear sender contrast.
    background: isAgent
      ? "var(--bg-paper-card, #faf6ef)"
      : "color-mix(in srgb, var(--accent) 7%, var(--bg-paper-deep, #e8dfcd))",
    border: `1px solid ${isAgent ? "var(--rule, #d6c8ad)" : "var(--rule, #d6c8ad)"}`,
    borderRadius: "6px",
    padding: "12px 16px",
    minWidth: 0,
  };

  const headerStyle: CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    marginBottom: "6px",
  };

  const bulletStyle: CSSProperties = {
    width: "8px",
    height: "8px",
    borderRadius: "999px",
    background: agentColour,
    flexShrink: 0,
    animation: streaming
      ? "msgbubble-pulse 220ms ease-in-out infinite alternate"
      : "none",
  };

  const nameStyle: CSSProperties = {
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "12px",
    fontWeight: 500,
    color: "var(--ink-soft, #5b5145)",
    letterSpacing: "0.02em",
  };

  const proseStyle: CSSProperties = {
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "14px",
    lineHeight: 1.6,
    color: "var(--ink, #2a2520)",
  };

  const footerStyle: CSSProperties = {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "8px",
    marginTop: "6px",
  };

  const timeStyle: CSSProperties = {
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "10px",
    color: "var(--ink-faint, #9c8e7e)",
  };

  const copyBtnStyle: CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: "4px",
    padding: "2px 7px",
    border: "1px solid var(--rule, #d6c8ad)",
    borderRadius: "3px",
    background: copied ? "color-mix(in srgb, var(--accent) 10%, transparent)" : "transparent",
    color: copied ? "var(--accent, #6b4f8a)" : "var(--ink-faint, #9c8e7e)",
    fontFamily: "var(--ff-mono, monospace)",
    fontSize: "10px",
    letterSpacing: "0.06em",
    cursor: "pointer",
    transition: "all 0.15s ease",
    flexShrink: 0,
  };

  return (
    <div style={wrapStyle}>
      <style>{`
        @keyframes msgbubble-pulse {
          0% { opacity: 1; transform: scale(1); }
          100% { opacity: 0.5; transform: scale(0.85); }
        }
        @keyframes msgbubble-spin {
          to { transform: rotate(360deg); }
        }
        .msg-bubble-prose p { margin: 0 0 8px; }
        .msg-bubble-prose p:last-child { margin-bottom: 0; }
        .msg-bubble-prose code {
          font-family: var(--ff-mono, "JetBrains Mono", monospace);
          font-size: 0.88em;
          padding: 1px 5px;
          border-radius: 3px;
          background: var(--bg-paper-deep, #e8dfcd);
          color: var(--accent-deep, #4a3666);
        }
        .msg-bubble-prose strong { font-weight: 600; }
        .msg-bubble-prose em { font-style: italic; }
        .msg-bubble-prose a { color: var(--accent, #6b4f8a); text-decoration: underline; }
        .msg-bubble-prose ul, .msg-bubble-prose ol { margin: 4px 0 8px; padding-left: 20px; }
        .msg-bubble-prose li { margin: 2px 0; }
        .prose-copy-btn:hover { border-color: var(--accent-soft, #b7a4c9) !important; color: var(--accent, #6b4f8a) !important; }
        @media (prefers-reduced-motion: reduce) {
          * { animation: none !important; }
        }
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
          {isAgent && (
            <div style={headerStyle}>
              <span style={bulletStyle} aria-hidden="true" />
              <span style={nameStyle}>{agentName}</span>
            </div>
          )}
          <div className="msg-bubble-prose" style={proseStyle}>
            <MarkdownRenderer markdown={markdown} t={t} />
          </div>
          <div style={footerStyle}>
            <span style={timeStyle}>{timestamp}</span>
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
                  <>
                    <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M1.5 5.5l2 2 5-5" />
                    </svg>
                    {t("chat:copy.done")}
                  </>
                ) : (
                  <>
                    <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <rect x="3.5" y="1" width="5.5" height="6.5" rx="1" />
                      <rect x="1" y="3.5" width="5.5" height="6.5" rx="1" />
                    </svg>
                    {t("chat:copy.label")}
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default MessageBubble;
