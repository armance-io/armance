import { type CSSProperties, type FC, useMemo } from "react";
import { marked } from "marked";

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

/* ─── Markdown renderer ──────────────────────────────────────────────────── */

const md = new marked.Marked({ gfm: true, breaks: true, async: false });

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
  const html = useMemo(
    () => md.parse(markdown, { async: false }) as string,
    [markdown],
  );

  const isAgent = role === "agent";

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
    background: isAgent
      ? "var(--bg-paper, #f4ede0)"
      : "var(--bg-paper-deep, #e8dfcd)",
    border: isAgent ? "1px solid var(--rule, #d6c8ad)" : "none",
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

  const spinnerStyle: CSSProperties = {
    width: "12px",
    height: "12px",
    border: "1.5px solid var(--rule, #d6c8ad)",
    borderTopColor: agentColour,
    borderRadius: "999px",
    animation: "msgbubble-spin 600ms linear infinite",
    flexShrink: 0,
  };

  const proseStyle: CSSProperties = {
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "14px",
    lineHeight: 1.6,
    color: "var(--ink, #2a2520)",
  };

  const timeStyle: CSSProperties = {
    fontFamily: "var(--ff-mono, 'JetBrains Mono', monospace)",
    fontSize: "10px",
    color: "var(--ink-faint, #9c8e7e)",
    marginTop: "6px",
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
              {streaming && (
                <>
                  <span
                    style={spinnerStyle}
                    role="status"
                    aria-label={t("chat:bubble.streaming_aria")}
                  />
                </>
              )}
            </div>
          )}
          <div
            className="msg-bubble-prose"
            style={proseStyle}
            dangerouslySetInnerHTML={{ __html: html }}
          />
          <div style={timeStyle}>{timestamp}</div>
        </div>
      </div>
    </div>
  );
};

export default MessageBubble;
