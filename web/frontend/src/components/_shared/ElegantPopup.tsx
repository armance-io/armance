"use client";

import { type FC, type ReactNode, useEffect } from "react";
import { tokens } from "./armance-tokens";

/**
 * The single modal/popup pattern for the app — centred card on a soft scrim,
 * Belle Époque framing. Use for confirmations and any blocking dialog so the
 * UX stays identical everywhere (never a window.confirm, never a bespoke box).
 */
export interface ElegantPopupProps {
  open: boolean;
  title: string;
  children?: ReactNode;
  /** Primary action label; omit to render an informational popup. */
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm?: () => void;
  onClose: () => void;
}

export const ElegantPopup: FC<ElegantPopupProps> = ({
  open,
  title,
  children,
  confirmLabel,
  cancelLabel,
  danger = false,
  onConfirm,
  onClose,
}) => {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const btn = (primary: boolean) => ({
    height: tokens.controlH,
    padding: "0 16px",
    borderRadius: tokens.radiusSm,
    fontFamily: tokens.ffSans,
    fontSize: 13,
    cursor: "pointer",
    border: primary ? "none" : `1px solid ${tokens.rule}`,
    background: primary ? (danger ? tokens.danger : tokens.accent) : "transparent",
    color: primary ? "#fff" : tokens.inkSoft,
  });

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1100,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(42, 37, 32, 0.32)",
        backdropFilter: "blur(2px)",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "min(440px, calc(100vw - 32px))",
          background: tokens.bgPaperCard,
          borderRadius: tokens.radiusPop,
          boxShadow: tokens.shadowPop,
          padding: "24px",
          animation: "armance-pop-in 180ms ease",
        }}
      >
        <h3 style={{
          margin: "0 0 12px",
          fontFamily: tokens.ffSerif,
          fontSize: 20,
          color: tokens.ink,
          fontWeight: 500,
        }}>
          {title}
        </h3>
        {children && (
          <div style={{ fontFamily: tokens.ffSans, fontSize: 13, color: tokens.inkSoft, lineHeight: 1.55 }}>
            {children}
          </div>
        )}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 20 }}>
          {confirmLabel && (
            <button type="button" style={btn(false)} onClick={onClose}>
              {cancelLabel ?? "Cancel"}
            </button>
          )}
          {confirmLabel ? (
            <button type="button" style={btn(true)} onClick={() => { onConfirm?.(); onClose(); }}>
              {confirmLabel}
            </button>
          ) : (
            <button type="button" style={btn(true)} onClick={onClose}>
              {cancelLabel ?? "OK"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default ElegantPopup;
