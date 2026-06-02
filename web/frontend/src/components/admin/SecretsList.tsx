import { type CSSProperties, type FC, useState } from "react";
import { tokens } from "../_shared/armance-tokens";
import { ElegantPopup } from "../_shared/ElegantPopup";

export interface SecretEntry {
  key: string;
  /** Full plaintext value — only fetched on reveal. */
  value: string;
  /** Last 4 of the value for the masked display. */
  last4: string;
}

export interface SecretsListProps {
  secrets: SecretEntry[];
  onEdit: (key: string, newValue: string) => Promise<void>;
  onDelete: (key: string) => Promise<void>;
  onReveal: (key: string) => Promise<string>;
  t: (key: string) => string;
}

export const SecretsList: FC<SecretsListProps> = ({
  secrets,
  onEdit,
  onDelete,
  onReveal,
  t,
}) => {
  const [popupSecret, setPopupSecret] = useState<{ key: string; value: string } | null>(null);
  const [clearValues, setClearValues] = useState<Record<string, string>>({});
  const [loadingReveal, setLoadingReveal] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null);

  const handleRevealClick = async (key: string) => {
    if (clearValues[key]) {
      setPopupSecret({ key, value: clearValues[key] });
    } else {
      setLoadingReveal(key);
      try {
        const val = await onReveal(key);
        setClearValues((prev) => ({ ...prev, [key]: val }));
        setPopupSecret({ key, value: val });
      } catch (err) {
        console.error(err);
      } finally {
        setLoadingReveal(null);
      }
    }
  };

  const wrap: CSSProperties = {
    background: tokens.bgPaperCard,
    border: `1px solid ${tokens.rule}`,
    fontFamily: tokens.ffSans,
    color: tokens.ink,
  };
  const head: CSSProperties = {
    display: "grid",
    gridTemplateColumns: "260px 1fr auto",
    padding: "12px 20px",
    borderBottom: `1px solid ${tokens.rule}`,
    background: tokens.bgPaperDeep,
    fontFamily: tokens.ffMono,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: tokens.inkSoft,
  };
  const row: CSSProperties = {
    display: "grid",
    gridTemplateColumns: "260px 1fr auto",
    padding: "12px 20px",
    borderBottom: `1px solid ${tokens.rule}`,
    alignItems: "center",
    gap: 12,
  };

  return (
    <div style={wrap}>
      <div style={head}>
        <span>{t("admin:secrets.col.key")}</span>
        <span>{t("admin:secrets.col.value")}</span>
        <span style={{ textAlign: "right" }}>{t("admin:secrets.col.actions")}</span>
      </div>

      {secrets.length === 0 && (
        <div style={{ padding: 40, textAlign: "center", color: tokens.inkFaint }}>
          {t("admin:secrets.empty")}
        </div>
      )}

      {secrets.map((s) => {
        const isBaseUrl = s.key.endsWith("_BASE_URL");
        const displayedValue = isBaseUrl ? s.value : `sk-***…${s.last4}`;

        return (
          <div key={s.key} style={row}>
            <code style={{ fontFamily: tokens.ffMono, fontSize: 13, color: tokens.ink }}>
              {s.key}
            </code>

            {editing === s.key ? (
              <input
                autoFocus
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                style={{
                  padding: "6px 10px",
                  border: `1px solid ${tokens.accent}`,
                  background: tokens.bgPaper,
                  fontFamily: tokens.ffMono,
                  fontSize: 13,
                  color: tokens.ink,
                }}
              />
            ) : (
              <code
                style={{
                  fontFamily: tokens.ffMono,
                  fontSize: 13,
                  color: tokens.inkSoft,
                  textAlign: "left",
                  justifySelf: "start",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {loadingReveal === s.key ? "…" : displayedValue}
              </code>
            )}

            <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
              {editing === s.key ? (
                <>
                  <IconBtn
                    label={t("admin:secrets.action.save")}
                    onClick={async () => {
                      await onEdit(s.key, editValue);
                      setEditing(null);
                    }}
                  >
                    ✓
                  </IconBtn>
                  <IconBtn
                    label={t("admin:secrets.action.cancel")}
                    onClick={() => setEditing(null)}
                  >
                    ✕
                  </IconBtn>
                </>
              ) : (
                <>
                  {!isBaseUrl && (
                    <IconBtn
                      label={t("admin:secrets.action.reveal")}
                      onClick={() => handleRevealClick(s.key)}
                      active={popupSecret?.key === s.key}
                    >
                      <EyeIcon crossed={popupSecret?.key === s.key} />
                    </IconBtn>
                  )}
                  <IconBtn
                    label={t("admin:secrets.action.edit")}
                    onClick={() => {
                      setEditing(s.key);
                      setEditValue(isBaseUrl ? s.value : (clearValues[s.key] || ""));
                    }}
                  >
                    ✎
                  </IconBtn>
                  <IconBtn
                    label={t("admin:secrets.action.delete")}
                    onClick={() => setConfirmingDelete(s.key)}
                    danger
                  >
                    🗑
                  </IconBtn>
                </>
              )}
            </div>
          </div>
        );
      })}

      {confirmingDelete && (
        <ConfirmModal
          message={t("admin:secrets.confirm_delete").replace(
            "{key}",
            confirmingDelete,
          )}
          confirmLabel={t("admin:secrets.action.delete")}
          cancelLabel={t("admin:secrets.action.cancel")}
          onCancel={() => setConfirmingDelete(null)}
          onConfirm={async () => {
            await onDelete(confirmingDelete);
            setConfirmingDelete(null);
          }}
        />
      )}

      {popupSecret && (
        <ElegantPopup
          open={true}
          title={popupSecret.key}
          onClose={() => setPopupSecret(null)}
          cancelLabel={t("common.close") || "Close"}
        >
          <div
            style={{
              wordBreak: "break-all",
              fontFamily: tokens.ffMono,
              fontSize: 13,
              color: tokens.ink,
              padding: "8px 0",
            }}
          >
            {popupSecret.value}
          </div>
        </ElegantPopup>
      )}
    </div>
  );
};

const EyeIcon: FC<{ crossed?: boolean }> = ({ crossed }) => (
  <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5z" />
    <circle cx="8" cy="8" r="2" />
    {crossed && <line x1="3" y1="3" x2="13" y2="13" stroke="currentColor" strokeWidth="1.5" />}
  </svg>
);

const IconBtn: FC<{
  label: string;
  danger?: boolean;
  active?: boolean;
  children: React.ReactNode;
  onClick?: () => void;
  onMouseDown?: () => void;
  onMouseUp?: () => void;
  onMouseLeave?: () => void;
}> = ({ label, danger, active, children, ...handlers }) => (
  <button
    type="button"
    aria-label={label}
    title={label}
    {...handlers}
    style={{
      width: 28,
      height: 28,
      display: "grid",
      placeItems: "center",
      border: `1px solid ${active ? "var(--accent, #6b4f8a)" : tokens.rule}`,
      background: active ? "color-mix(in srgb, var(--accent, #6b4f8a) 12%, transparent)" : "transparent",
      color: danger ? "var(--danger, #a44141)" : (active ? "var(--accent, #6b4f8a)" : tokens.inkSoft),
      cursor: "pointer",
      borderRadius: 4,
      transition: "all 0.15s ease",
    }}
  >
    {children}
  </button>
);

const ConfirmModal: FC<{
  message: string;
  confirmLabel: string;
  cancelLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
}> = ({ message, confirmLabel, cancelLabel, onConfirm, onCancel }) => (
  <div
    role="dialog"
    aria-modal="true"
    style={{
      position: "fixed",
      inset: 0,
      background: "rgba(42, 37, 32, 0.4)",
      display: "grid",
      placeItems: "center",
      zIndex: 100,
    }}
  >
    <div
      style={{
        background: tokens.bgPaperCard,
        border: `1px solid ${tokens.rule}`,
        padding: "28px 32px",
        maxWidth: 420,
        fontFamily: tokens.ffSans,
        color: tokens.ink,
      }}
    >
      <p style={{ margin: "0 0 24px", lineHeight: 1.5 }}>{message}</p>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
        <button
          type="button"
          onClick={onCancel}
          style={{
            padding: "8px 18px",
            border: `1px solid ${tokens.rule}`,
            background: "transparent",
            color: tokens.inkSoft,
            borderRadius: 999,
            fontFamily: tokens.ffSans,
            fontSize: 13,
            cursor: "pointer",
          }}
        >
          {cancelLabel}
        </button>
        <button
          type="button"
          onClick={onConfirm}
          style={{
            padding: "8px 18px",
            border: "1px solid var(--danger, #a44141)",
            background: "var(--danger, #a44141)",
            color: tokens.bgPaperCard,
            borderRadius: 999,
            fontFamily: tokens.ffSans,
            fontSize: 13,
            cursor: "pointer",
          }}
        >
          {confirmLabel}
        </button>
      </div>
    </div>
  </div>
);

export default SecretsList;
