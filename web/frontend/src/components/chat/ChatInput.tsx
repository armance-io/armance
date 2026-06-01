import {
  type CSSProperties,
  type FC,
  useState,
  useCallback,
  useRef,
  useEffect,
  type KeyboardEvent,
  type ChangeEvent,
} from "react";
import { onMention } from "@/lib/mentionBus";

/* ─── Types ──────────────────────────────────────────────────────────────── */

export interface ChatInputProps {
  placeholder: string;
  disabled?: boolean;
  busyAgentName?: string;
  busyAgentColour?: string;
  onSubmit: (text: string) => void;
  t: (key: string) => string;
}

/* ─── Component ──────────────────────────────────────────────────────────── */

export const ChatInput: FC<ChatInputProps> = ({
  placeholder,
  disabled = false,
  busyAgentName,
  busyAgentColour,
  onSubmit,
  t,
}) => {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const isBusy = !!busyAgentName;
  const canSend = value.trim().length > 0 && !disabled;

  /* Auto-grow textarea */
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const maxH = 6 * 24; /* 6 rows × ~24px line-height */
    el.style.height = `${Math.min(el.scrollHeight, maxH)}px`;
  }, [value]);

  const handleSubmit = useCallback(() => {
    if (!canSend) return;
    onSubmit(value.trim());
    setValue("");
  }, [canSend, onSubmit, value]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      // Enter sends; Shift+Enter inserts a newline (so ``` fences, inline
      // `code`, and "- bullet" lists are easy to type over multiple lines).
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  const handleChange = useCallback((e: ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value);
  }, []);

  /* Sidebar Staff click → inject `@Agent ` and focus, no navigation. */
  useEffect(() => {
    return onMention((mention) => {
      setValue((prev) => {
        const sep = prev && !prev.endsWith(" ") ? " " : "";
        return `${prev}${sep}${mention}`;
      });
      textareaRef.current?.focus();
    });
  }, []);

  /* ── Styles ── */

  const rootStyle: CSSProperties = {
    position: "sticky",
    bottom: 0,
    background: "var(--bg-paper, #f4ede0)",
    borderTop: "1px solid var(--rule, #d6c8ad)",
    padding: "0",
  };

  const busyBarStyle: CSSProperties = {
    display: isBusy ? "flex" : "none",
    alignItems: "center",
    gap: "8px",
    padding: "6px 16px",
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "13px",
    fontStyle: "italic",
    color: "var(--ink-soft, #5b5145)",
  };

  const busyDotStyle: CSSProperties = {
    width: "6px",
    height: "6px",
    borderRadius: "999px",
    background: busyAgentColour ?? "var(--accent, #6b4f8a)",
    animation: "chatinput-pulse 1.4s ease-in-out infinite",
    flexShrink: 0,
  };

  // BUG-08: send button vertically centred with the input; wrapper background
  // matches the page (rootStyle uses --bg-paper), no contrasting box.
  const inputRowStyle: CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    padding: "10px 16px 14px",
  };

  const textareaStyle: CSSProperties = {
    flex: 1,
    minHeight: "24px",
    maxHeight: `${6 * 24}px`,
    resize: "none",
    border: "1px solid var(--rule, #d6c8ad)",
    borderRadius: "8px",
    padding: "10px 14px",
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "14px",
    lineHeight: "24px",
    color: "var(--ink, #2a2520)",
    background: "var(--bg-paper-card, #faf6ef)",
    outline: "none",
    transition: "border-color 160ms ease",
  };

  const sendBtnStyle: CSSProperties = {
    width: "36px",
    height: "36px",
    borderRadius: "999px",
    border: "none",
    background: canSend
      ? "var(--accent, #6b4f8a)"
      : "var(--rule, #d6c8ad)",
    color: canSend
      ? "var(--bg-paper, #f4ede0)"
      : "var(--ink-faint, #9c8e7e)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
    cursor: canSend ? "pointer" : "default",
    transition: "background 160ms ease, color 160ms ease",
  };

  return (
    <div style={rootStyle}>
      <style>{`
        @keyframes chatinput-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
        @media (prefers-reduced-motion: reduce) {
          * { animation: none !important; transition: none !important; }
        }
      `}</style>

      <div style={busyBarStyle} aria-live="polite">
        <span style={busyDotStyle} aria-hidden="true" />
        <span>
          {t("chat:input.busy_label").replace(
            "{name}",
            busyAgentName ?? "",
          )}
        </span>
      </div>

      <div style={inputRowStyle}>
        <textarea
          ref={textareaRef}
          style={textareaStyle}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          aria-label={t("chat:input.placeholder")}
          onFocus={(e) => {
            e.currentTarget.style.borderColor =
              "var(--accent, #6b4f8a)";
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderColor =
              "var(--rule, #d6c8ad)";
          }}
        />
        <button
          style={sendBtnStyle}
          onClick={handleSubmit}
          disabled={!canSend}
          aria-label={t("chat:input.send_aria")}
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M14 2L7 9" />
            <path d="M14 2l-5 12-2-5-5-2 12-5z" />
          </svg>
        </button>
      </div>
    </div>
  );
};

export default ChatInput;
