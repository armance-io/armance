"use client";

import {
  type CSSProperties,
  type FC,
  type ReactNode,
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";
import { tokens } from "./armance-tokens";

/**
 * The single toast surface for the whole app. Elegant, calm, Belle Époque:
 * one pattern, used everywhere a transient confirmation is needed (e.g. index
 * launched, secret saved). Never roll a bespoke notification.
 */
export type ToastKind = "info" | "success" | "error";

interface ToastItem {
  id: number;
  kind: ToastKind;
  message: string;
}

interface ToastApi {
  toast: (message: string, kind?: ToastKind) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    // Safe no-op outside a provider (e.g. unit tests that don't wrap).
    return { toast: () => undefined };
  }
  return ctx;
}

const ACCENT: Record<ToastKind, string> = {
  info: tokens.accent,
  success: "var(--accent)",
  error: tokens.danger,
};

const GLYPH: Record<ToastKind, string> = {
  info: "❦",
  success: "✓",
  error: "✗",
};

export const ToastProvider: FC<{ children: ReactNode }> = ({ children }) => {
  const [items, setItems] = useState<ToastItem[]>([]);

  const toast = useCallback((message: string, kind: ToastKind = "info") => {
    const id = Date.now() + Math.random();
    setItems((prev) => [...prev, { id, kind, message }]);
    window.setTimeout(() => {
      setItems((prev) => prev.filter((t) => t.id !== id));
    }, 3600);
  }, []);

  const api = useMemo(() => ({ toast }), [toast]);

  const stackStyle: CSSProperties = {
    position: "fixed",
    bottom: 24,
    right: 24,
    display: "flex",
    flexDirection: "column",
    gap: 10,
    zIndex: 1000,
    pointerEvents: "none",
  };

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div style={stackStyle} aria-live="polite" role="status">
        {items.map((t) => (
          <div
            key={t.id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              minWidth: 220,
              maxWidth: 360,
              padding: "12px 16px",
              background: tokens.bgPaperCard,
              color: tokens.ink,
              fontFamily: tokens.ffSans,
              fontSize: 13,
              borderRadius: tokens.radiusMd,
              borderLeft: `3px solid ${ACCENT[t.kind]}`,
              boxShadow: tokens.shadowPop,
              animation: "armance-toast-in 200ms ease",
            }}
          >
            <span style={{ color: ACCENT[t.kind], fontFamily: tokens.ffSerif, fontSize: 15 }}>
              {GLYPH[t.kind]}
            </span>
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
};

export default ToastProvider;
