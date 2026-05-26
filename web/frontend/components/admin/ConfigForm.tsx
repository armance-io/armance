import { type CSSProperties, type FC, useState } from "react";
import { tokens } from "../_shared/armance-tokens";

export interface ConfigValues {
  default_provider: string;
  default_model: string;
  budget_effort: "free-first" | "low" | "medium" | "high";
  language: string;
  judge_model: string;
  log_level: "debug" | "info" | "warn" | "error";
}

export interface ConfigFormProps {
  values: ConfigValues;
  modelOptions: string[];
  judgeModelOptions: string[];
  languageOptions: string[];
  onSave: (values: ConfigValues) => Promise<void>;
  t: (key: string) => string;
}

const BUDGETS = ["free-first", "low", "medium", "high"] as const;
const LOG_LEVELS = ["debug", "info", "warn", "error"] as const;

export const ConfigForm: FC<ConfigFormProps> = ({
  values,
  modelOptions,
  judgeModelOptions,
  languageOptions,
  onSave,
  t,
}) => {
  const [draft, setDraft] = useState<ConfigValues>(values);
  const [errors, setErrors] = useState<Partial<Record<keyof ConfigValues, string>>>({});
  const [saving, setSaving] = useState(false);

  const set = <K extends keyof ConfigValues>(k: K, v: ConfigValues[K]) =>
    setDraft((d) => ({ ...d, [k]: v }));

  const validate = () => {
    const e: Partial<Record<keyof ConfigValues, string>> = {};
    if (!draft.default_model) e.default_model = t("admin:config.err.required");
    if (!draft.judge_model) e.judge_model = t("admin:config.err.required");
    if (!draft.language) e.language = t("admin:config.err.required");
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSave = async () => {
    if (!validate()) return;
    setSaving(true);
    try {
      await onSave(draft);
    } finally {
      setSaving(false);
    }
  };

  const wrap: CSSProperties = {
    background: tokens.bgPaperCard,
    border: `1px solid ${tokens.rule}`,
    padding: "32px 40px",
    fontFamily: tokens.ffSans,
    color: tokens.ink,
    maxWidth: 640,
  };
  const row: CSSProperties = { display: "grid", gap: 6, marginBottom: 20 };
  const label: CSSProperties = {
    fontSize: 12,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: tokens.inkSoft,
    fontFamily: tokens.ffMono,
  };
  const inputBase: CSSProperties = {
    padding: "10px 12px",
    border: `1px solid ${tokens.rule}`,
    background: tokens.bgPaper,
    fontFamily: tokens.ffMono,
    fontSize: 13,
    color: tokens.ink,
  };
  const readonlyVal: CSSProperties = {
    ...inputBase,
    background: tokens.bgPaperDeep,
    color: tokens.inkSoft,
  };
  const errStyle: CSSProperties = {
    fontSize: 12,
    color: "var(--danger, #a44141)",
    fontStyle: "italic",
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        handleSave();
      }}
      style={wrap}
    >
      <h2
        style={{
          fontFamily: tokens.ffSerif,
          fontSize: 28,
          margin: "0 0 24px",
          letterSpacing: "-0.01em",
        }}
      >
        {t("admin:config.title")}
      </h2>

      <div style={row}>
        <label style={label}>{t("admin:config.default_provider")}</label>
        <div style={readonlyVal}>{draft.default_provider || "—"}</div>
      </div>

      <div style={row}>
        <label style={label}>{t("admin:config.default_model")}</label>
        <select
          style={inputBase}
          value={draft.default_model}
          onChange={(e) => set("default_model", e.target.value)}
        >
          <option value="">—</option>
          {modelOptions.map((m) => (
            <option key={m}>{m}</option>
          ))}
        </select>
        {errors.default_model && <span style={errStyle}>{errors.default_model}</span>}
      </div>

      <div style={row}>
        <label style={label}>{t("admin:config.budget_effort")}</label>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {BUDGETS.map((b) => (
            <Chip
              key={b}
              active={draft.budget_effort === b}
              onClick={() => set("budget_effort", b)}
              label={t(`admin:config.budget.${b}`)}
            />
          ))}
        </div>
      </div>

      <div style={row}>
        <label style={label}>{t("admin:config.language")}</label>
        <select
          style={inputBase}
          value={draft.language}
          onChange={(e) => set("language", e.target.value)}
        >
          <option value="">—</option>
          {languageOptions.map((l) => (
            <option key={l}>{l}</option>
          ))}
        </select>
        {errors.language && <span style={errStyle}>{errors.language}</span>}
      </div>

      <div style={row}>
        <label style={label}>{t("admin:config.judge_model")}</label>
        <select
          style={inputBase}
          value={draft.judge_model}
          onChange={(e) => set("judge_model", e.target.value)}
        >
          <option value="">—</option>
          {judgeModelOptions.map((m) => (
            <option key={m}>{m}</option>
          ))}
        </select>
        {errors.judge_model && <span style={errStyle}>{errors.judge_model}</span>}
      </div>

      <div style={row}>
        <label style={label}>{t("admin:config.log_level")}</label>
        <div style={{ display: "flex", gap: 8 }}>
          {LOG_LEVELS.map((lv) => (
            <Chip
              key={lv}
              active={draft.log_level === lv}
              onClick={() => set("log_level", lv)}
              label={lv}
              mono
            />
          ))}
        </div>
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 24 }}>
        <button
          type="submit"
          disabled={saving}
          style={{
            padding: "10px 22px",
            borderRadius: 999,
            border: `1px solid ${tokens.accent}`,
            background: tokens.accent,
            color: tokens.bgPaperCard,
            fontFamily: tokens.ffSans,
            fontSize: 13,
            fontWeight: 500,
            cursor: saving ? "wait" : "pointer",
          }}
        >
          {saving ? t("admin:config.saving") : t("admin:config.save")}
        </button>
      </div>
    </form>
  );
};

const Chip: FC<{
  active: boolean;
  onClick: () => void;
  label: string;
  mono?: boolean;
}> = ({ active, onClick, label, mono }) => (
  <button
    type="button"
    onClick={onClick}
    style={{
      padding: "6px 14px",
      borderRadius: 999,
      border: `1px solid ${active ? tokens.accent : tokens.rule}`,
      background: active ? tokens.accent : "transparent",
      color: active ? tokens.bgPaperCard : tokens.inkSoft,
      fontFamily: mono ? tokens.ffMono : tokens.ffSans,
      fontSize: 12,
      cursor: "pointer",
      textTransform: mono ? "uppercase" : "none",
      letterSpacing: mono ? "0.06em" : "normal",
    }}
  >
    {label}
  </button>
);

export default ConfigForm;
