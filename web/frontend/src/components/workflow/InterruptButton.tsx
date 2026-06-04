import {
  type CSSProperties,
  type FC,
  useState,
  useCallback,
  useRef,
  useEffect,
} from "react";

/* ─── Types ──────────────────────────────────────────────────────────────── */

type RunStatus = "running" | "completed" | "failed" | "cancelled";

export interface InterruptButtonProps {
  runId: string;
  status: RunStatus;
  onInterrupt: (runId: string) => Promise<void>;
  t: (key: string) => string;
}

type ButtonState = "idle" | "confirming" | "submitting" | "error";

/* ─── Component ──────────────────────────────────────────────────────────── */

export const InterruptButton: FC<InterruptButtonProps> = ({
  runId,
  status,
  onInterrupt,
  t,
}) => {
  const [state, setState] = useState<ButtonState>("idle");
  const [errorMessage, setErrorMessage] = useState<string>("");

  const [isBtnHovered, setIsBtnHovered] = useState(false);
  const [isYesHovered, setIsYesHovered] = useState(false);
  const [isNoHovered, setIsNoHovered] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const isEnabled = status === "running" && state !== "submitting";

  /* ─── Handlers ─────────────────────────────────────────────────────────── */

  const handleTriggerClick = useCallback(() => {
    if (!isEnabled) return;
    if (state === "idle" || state === "error") {
      setState("confirming");
    } else {
      setState("idle");
    }
  }, [isEnabled, state]);

  const handleCancel = useCallback(() => {
    setState("idle");
    triggerRef.current?.focus();
  }, []);

  const handleConfirm = useCallback(async () => {
    if (!isEnabled) return;
    setState("submitting");
    setErrorMessage("");
    try {
      await onInterrupt(runId);
      setState("idle");
    } catch (err: unknown) {
      setState("error");
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage(t("workflow:interrupt.error"));
      }
    }
  }, [isEnabled, onInterrupt, runId, t]);

  /* ─── Effects for Accessibility and Click Outside ──────────────────────── */

  useEffect(() => {
    if (state !== "confirming" && state !== "error") return;

    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setState("idle");
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [state]);

  useEffect(() => {
    if (state !== "confirming") return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setState("idle");
        triggerRef.current?.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [state]);

  /* ─── Styles ───────────────────────────────────────────────────────────── */

  const containerStyle: CSSProperties = {
    position: "relative",
    display: "inline-block",
  };

  const btnStyle: CSSProperties = {
    height: "32px",
    padding: "0 12px",
    border: `1px solid ${isBtnHovered && isEnabled ? "var(--accent, #6b4f8a)" : "var(--rule, #d6c8ad)"}`,
    background: "var(--bg-paper, #f4ede0)",
    color: isEnabled ? "var(--ink, #2a2520)" : "var(--ink-soft, #5b5145)",
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "13px",
    fontWeight: 500,
    borderRadius: "2px",
    display: "inline-flex",
    alignItems: "center",
    gap: "8px",
    cursor: isEnabled ? "pointer" : "not-allowed",
    opacity: isEnabled ? 1 : 0.5,
    transition: "border-color 120ms ease, color 120ms ease, background 120ms ease",
    outline: "none",
  };

  const modalStyle: CSSProperties = {
    position: "absolute",
    right: 0,
    top: "calc(100% + 6px)",
    width: "240px",
    padding: "12px 14px",
    border: "1px solid var(--rule, #d6c8ad)",
    borderRadius: "2px",
    background: "var(--bg-paper-card, #faf6ef)",
    zIndex: 20,
    display: "flex",
    flexDirection: "column",
    gap: "10px",
    boxShadow: "none",
  };

  const promptStyle: CSSProperties = {
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "13px",
    color: "var(--ink, #2a2520)",
    margin: 0,
    lineHeight: 1.45,
  };

  const actionsStyle: CSSProperties = {
    display: "flex",
    justifyContent: "flex-end",
    gap: "8px",
  };

  const yesBtnStyle: CSSProperties = {
    padding: "6px 12px",
    border: "none",
    borderRadius: "2px",
    background: isYesHovered ? "var(--accent-deep, #4a3666)" : "var(--accent, #6b4f8a)",
    color: "var(--bg-paper, #f4ede0)",
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "12px",
    fontWeight: 500,
    cursor: "pointer",
    transition: "background 120ms ease",
  };

  const noBtnStyle: CSSProperties = {
    padding: "5px 11px",
    border: "1px solid var(--rule, #d6c8ad)",
    borderRadius: "2px",
    background: isNoHovered ? "var(--bg-paper-deep, #e8dfcd)" : "transparent",
    color: "var(--ink-soft, #5b5145)",
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "12px",
    fontWeight: 500,
    cursor: "pointer",
    transition: "background 120ms ease",
  };

  const tooltipStyle: CSSProperties = {
    position: "absolute",
    right: 0,
    top: "calc(100% + 6px)",
    width: "240px",
    padding: "8px 12px",
    border: "1px solid var(--danger, #a44141)",
    borderRadius: "2px",
    background: "var(--bg-paper-card, #faf6ef)",
    color: "var(--danger, #a44141)",
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "12px",
    zIndex: 20,
    lineHeight: 1.4,
    cursor: "pointer",
  };

  const spinnerStyle: CSSProperties = {
    width: "12px",
    height: "12px",
    border: "1.5px solid var(--rule, #d6c8ad)",
    borderTopColor: "var(--accent, #6b4f8a)",
    borderRadius: "999px",
    flexShrink: 0,
    display: "inline-block",
  };

  return (
    <div ref={containerRef} style={containerStyle}>
      <style>{`
        @keyframes interrupt-spin {
          to { transform: rotate(360deg); }
        }
        @keyframes interrupt-fade-in {
          from {
            opacity: 0;
            transform: translateY(-4px) scale(0.98);
          }
          to {
            opacity: 1;
            transform: translateY(0) scale(1);
          }
        }
        .interrupt-spinner {
          animation: interrupt-spin 600ms linear infinite;
        }
        .interrupt-popover {
          animation: interrupt-fade-in 150ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
        @media (prefers-reduced-motion: reduce) {
          * {
            animation: none !important;
            transition: none !important;
          }
        }
      `}</style>

      <button
        ref={triggerRef}
        style={btnStyle}
        onClick={handleTriggerClick}
        disabled={!isEnabled}
        aria-haspopup="dialog"
        aria-expanded={state === "confirming"}
        aria-label={t("workflow:interrupt.label")}
        onMouseEnter={() => setIsBtnHovered(true)}
        onMouseLeave={() => setIsBtnHovered(false)}
        onFocus={() => setIsBtnHovered(true)}
        onBlur={() => setIsBtnHovered(false)}
      >
        {state === "submitting" ? (
          <span
            className="interrupt-spinner"
            style={spinnerStyle}
            role="status"
            aria-hidden="true"
          />
        ) : (
          <span style={{ fontSize: "14px", lineHeight: 1 }} aria-hidden="true">
            ⏹
          </span>
        )}
        <span>{t("workflow:interrupt.label")}</span>
      </button>

      {/* Inline Confirm Modal */}
      {state === "confirming" && (
        <div
          className="interrupt-popover"
          style={modalStyle}
          role="alertdialog"
          aria-modal="true"
          aria-label={t("workflow:interrupt.confirm_title")}
        >
          <p style={promptStyle}>{t("workflow:interrupt.confirm_title")}</p>
          <div style={actionsStyle}>
            <button
              data-testid="interrupt-cancel"
              style={noBtnStyle}
              onClick={handleCancel}
              onMouseEnter={() => setIsNoHovered(true)}
              onMouseLeave={() => setIsNoHovered(false)}
              onFocus={() => setIsNoHovered(true)}
              onBlur={() => setIsNoHovered(false)}
            >
              {t("workflow:interrupt.confirm_no")}
            </button>
            <button
              data-testid="interrupt-confirm"
              style={yesBtnStyle}
              onClick={handleConfirm}
              onMouseEnter={() => setIsYesHovered(true)}
              onMouseLeave={() => setIsYesHovered(false)}
              onFocus={() => setIsYesHovered(true)}
              onBlur={() => setIsYesHovered(false)}
            >
              {t("workflow:interrupt.confirm_yes")}
            </button>
          </div>
        </div>
      )}

      {/* Error Tooltip */}
      {state === "error" && (
        <div
          className="interrupt-popover"
          style={tooltipStyle}
          role="tooltip"
          onClick={() => setState("idle")}
          aria-live="polite"
        >
          {errorMessage || t("workflow:interrupt.error")}
        </div>
      )}
    </div>
  );
};

export default InterruptButton;
