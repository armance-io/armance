import { type CSSProperties, type FC, useState, useEffect } from "react";
import { tokens } from "../_shared/armance-tokens";

type Level = "INFO" | "DEBUG" | "WARN" | "ERROR";

export interface LogLevelToggleProps {
  current: Level;
  onChange: (level: Level) => Promise<void>;
  t: (key: string) => string;
}

const LEVELS: Level[] = ["DEBUG", "INFO", "WARN", "ERROR"];

export const LogLevelToggle: FC<LogLevelToggleProps> = ({ current, onChange, t }) => {
  const [active, setActive] = useState<Level>(current);
  const [saving, setSaving] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  useEffect(() => {
    if (!showConfirm) return;
    const timer = setTimeout(() => {
      setShowConfirm(false);
    }, 3000);
    return () => clearTimeout(timer);
  }, [showConfirm]);

  const wrap: CSSProperties = {
    display: "flex",
    gap: 8,
    alignItems: "center",
    fontFamily: tokens.ffMono,
    fontSize: 13,
  };

  const label: CSSProperties = { color: tokens.inkSoft, marginRight: 8 };

  return (
    <div style={wrap}>
      <span style={label}>{t("admin:logs.level")}</span>
      {LEVELS.map((lvl) => (
        <button
          key={lvl}
          disabled={saving}
          onClick={async () => {
            setSaving(true);
            try {
              await onChange(lvl);
              setActive(lvl);
              setShowConfirm(true);
            } finally {
              setSaving(false);
            }
          }}
          style={{
            padding: "4px 12px",
            border: `1px solid ${active === lvl ? tokens.accent : tokens.rule}`,
            background: active === lvl ? tokens.accent : "transparent",
            color: active === lvl ? "#fff" : tokens.ink,
            cursor: saving ? "not-allowed" : "pointer",
            fontFamily: tokens.ffMono,
            fontSize: 12,
          }}
        >
          {lvl}
        </button>
      ))}

      {showConfirm && (
        <div
          role="dialog"
          aria-modal="true"
          onClick={() => setShowConfirm(false)}
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 10000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "rgba(42, 37, 32, 0.15)",
            backdropFilter: "blur(2px)",
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "var(--bg-paper-card, #faf6ef)",
              border: "1px solid var(--rule, #d6c8ad)",
              padding: "24px 32px",
              borderRadius: "2px",
              boxShadow: "0 12px 28px rgba(0,0,0,0.12)",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "12px",
              maxWidth: "90%",
              width: "360px",
              textAlign: "center",
            }}
          >
            <span style={{ fontSize: "24px", color: "var(--accent, #6b4f8a)" }}>❦</span>
            <h3 style={{
              fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
              fontSize: "20px",
              margin: 0,
              color: "var(--ink, #2a2520)",
            }}>
              {t("admin:logs.level_changed_title") || "Confirmation"}
            </h3>
            <p style={{
              fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
              fontSize: "14px",
              color: "var(--ink-soft, #5b5145)",
              margin: 0,
            }}>
              {t("admin:logs.level_changed_desc")?.replace("{level}", active) || `Niveau de log mis à jour : ${active}`}
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default LogLevelToggle;
