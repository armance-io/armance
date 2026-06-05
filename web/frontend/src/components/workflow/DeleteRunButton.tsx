import {
  type CSSProperties,
  type FC,
  useState,
  useCallback,
  useRef,
  useEffect,
} from "react";

import type { RunStatus } from "@/lib/runStatus";

/* ─── Types ──────────────────────────────────────────────────────────────── */

export interface DeleteRunButtonProps {
  runId: string;
  status: RunStatus;
  onDelete: (runId: string) => Promise<void>;
  t: (key: string) => string;
}

type ButtonState = "idle" | "confirming" | "submitting" | "error";

/* ─── Component ──────────────────────────────────────────────────────────── */

export const DeleteRunButton: FC<DeleteRunButtonProps> = ({
  runId,
  status,
  onDelete,
  t,
}) => {
  const [state, setState] = useState<ButtonState>("idle");
  const [errorMessage, setErrorMessage] = useState<string>("");

  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // A run still in flight (queued/working/running) can't be deleted.
  const isBlocked = status === "running" || status === "working" || status === "queued";
  const isEnabled = !isBlocked && state !== "submitting";

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
      await onDelete(runId);
      setState("idle");
    } catch (err: unknown) {
      setState("error");
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage(t("workflow:delete.error"));
      }
    }
  }, [isEnabled, onDelete, runId, t]);

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
    width: "24px",
    height: "24px",
    padding: 0,
    border: "none",
    background: "transparent",
    color: "var(--ink-soft, #5b5145)",
    borderRadius: "2px",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    cursor: isEnabled ? "pointer" : "not-allowed",
    opacity: isBlocked ? 0.4 : isEnabled ? 1 : 0.6,
    transition: "color 120ms ease, opacity 120ms ease",
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

  const titleStyle: CSSProperties = {
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "13px",
    fontWeight: 600,
    color: "var(--ink, #2a2520)",
    margin: 0,
    lineHeight: 1.4,
  };

  const hintStyle: CSSProperties = {
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "11px",
    color: "var(--ink-soft, #5b5145)",
    margin: 0,
    lineHeight: 1.4,
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
    background: "var(--accent, #6b4f8a)",
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
    background: "transparent",
    color: "var(--ink-soft, #5b5145)",
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "12px",
    fontWeight: 500,
    cursor: "pointer",
    transition: "background 120ms ease",
  };

  const blockedTooltipStyle: CSSProperties = {
    position: "absolute",
    right: 0,
    top: "calc(100% + 6px)",
    padding: "6px 10px",
    border: "1px solid var(--rule, #d6c8ad)",
    borderRadius: "2px",
    background: "var(--bg-paper-card, #faf6ef)",
    color: "var(--ink-soft, #5b5145)",
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "11px",
    zIndex: 20,
    whiteSpace: "nowrap",
    pointerEvents: "none",
  };

  const errorTooltipStyle: CSSProperties = {
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
    width: "14px",
    height: "14px",
    border: "1.5px solid var(--rule, #d6c8ad)",
    borderTopColor: "var(--accent, #6b4f8a)",
    borderRadius: "999px",
    flexShrink: 0,
    display: "inline-block",
  };

  return (
    <div ref={containerRef} style={containerStyle}>
      <style>{`
        @keyframes delete-spin {
          to { transform: rotate(360deg); }
        }
        @keyframes delete-fade-in {
          from {
            opacity: 0;
            transform: translateY(-4px) scale(0.98);
          }
          to {
            opacity: 1;
            transform: translateY(0) scale(1);
          }
        }
        .delete-spinner {
          animation: delete-spin 600ms linear infinite;
        }
        .delete-popover {
          animation: delete-fade-in 150ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
        .delete-trigger:hover:not([aria-disabled="true"]),
        .delete-trigger:focus:not([aria-disabled="true"]) {
          color: var(--accent, #6b4f8a) !important;
        }
        .delete-btn-yes:hover,
        .delete-btn-yes:focus {
          background: var(--accent-deep, #4a3666) !important;
          outline: none;
        }
        .delete-btn-no:hover,
        .delete-btn-no:focus {
          background: var(--bg-paper-deep, #e8dfcd) !important;
          outline: none;
        }
        .delete-blocked-tooltip {
          display: none;
        }
        .delete-trigger:hover + .delete-blocked-tooltip,
        .delete-trigger:focus + .delete-blocked-tooltip {
          display: block;
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
        className="delete-trigger"
        style={btnStyle}
        onClick={handleTriggerClick}
        aria-haspopup={isBlocked ? undefined : "dialog"}
        aria-expanded={state === "confirming"}
        aria-label={t("workflow:delete.aria")}
        aria-disabled={isBlocked ? "true" : undefined}
      >
        {state === "submitting" ? (
          <span
            className="delete-spinner"
            style={spinnerStyle}
            role="status"
            aria-hidden="true"
          />
        ) : (
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            <line x1="10" y1="11" x2="10" y2="17" />
            <line x1="14" y1="11" x2="14" y2="17" />
          </svg>
        )}
      </button>

      {/* Blocked Active Tooltip */}
      {isBlocked && (
        <div
          className="delete-popover delete-blocked-tooltip"
          style={blockedTooltipStyle}
          role="tooltip"
        >
          {t("workflow:delete.blocked_active")}
        </div>
      )}

      {/* Inline Confirm Modal */}
      {state === "confirming" && (
        <div
          className="delete-popover"
          style={modalStyle}
          role="alertdialog"
          aria-modal="true"
          aria-label={t("workflow:delete.confirm_title")}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
            <p style={titleStyle}>{t("workflow:delete.confirm_title")}</p>
            <p style={hintStyle}>{t("workflow:delete.confirm_hint")}</p>
          </div>
          <div style={actionsStyle}>
            <button
              className="delete-btn-no"
              style={noBtnStyle}
              onClick={handleCancel}
            >
              {t("workflow:delete.confirm_no")}
            </button>
            <button
              className="delete-btn-yes"
              style={yesBtnStyle}
              onClick={handleConfirm}
            >
              {t("workflow:delete.confirm_yes")}
            </button>
          </div>
        </div>
      )}

      {/* Error Tooltip */}
      {state === "error" && (
        <div
          className="delete-popover"
          style={errorTooltipStyle}
          role="tooltip"
          onClick={() => setState("idle")}
          aria-live="polite"
        >
          {errorMessage || t("workflow:delete.error")}
        </div>
      )}
    </div>
  );
};

export default DeleteRunButton;
