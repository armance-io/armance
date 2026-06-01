import { type CSSProperties, type FC, useState } from "react";
import { tokens } from "../_shared/armance-tokens";
import { providerLabel } from "@/lib/providerLabels";

export interface ConfigValues {
  default_provider: string;
  default_model: string;
  budget_effort: "free-first" | "low" | "medium" | "high";
  language: string;
  providers?: Array<{ name: string; base_url?: string | null }>;
}

export interface ConfigFormProps {
  values: ConfigValues;
  providerOptions: string[];
  modelOptionsByProvider: Record<string, string[]>;
  languageOptions: string[];
  onSave: (values: ConfigValues) => Promise<void>;
  t: (key: string) => string;
}

const BUDGETS = ["free-first", "low", "medium", "high"] as const;

export const ConfigForm: FC<ConfigFormProps> = ({
  values,
  providerOptions,
  modelOptionsByProvider,
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
         <select
           style={inputBase}
           value={draft.default_provider}
           onChange={(e) => {
             const nextProv = e.target.value;
             setDraft((d) => ({
               ...d,
               default_provider: nextProv,
               default_model: "", // Clear model when provider changes to enforce cascade
             }));
           }}
         >
           {providerOptions.map((p) => (
             <option key={p} value={p}>
               {providerLabel(p)}
             </option>
           ))}
         </select>
      </div>

      {/* Configured Providers Section */}
      <div style={row}>
        <label style={label}>{t("admin:config.providers")}</label>
        <div style={{ display: "grid", gap: 10 }}>
          {draft.providers && draft.providers.length > 0 ? (
            draft.providers.map((prov) => {
              const isDefault = prov.name === draft.default_provider;
              return (
                <div
                  key={prov.name}
                  style={{
                    ...readonlyVal,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "12px 16px",
                    border: isDefault ? `1px solid var(--accent, #6b4f8a)` : `1px solid ${tokens.rule}`,
                    background: isDefault ? "color-mix(in srgb, var(--accent, #6b4f8a) 4%, var(--bg-paper-card))" : tokens.bgPaperDeep,
                  }}
                >
                  <div>
                    <span style={{ fontWeight: 600, fontFamily: tokens.ffSans, color: tokens.ink }}>{providerLabel(prov.name)}</span>
                    {prov.base_url && (
                      <span style={{ fontSize: 11, marginLeft: 8, color: tokens.inkSoft, fontFamily: tokens.ffMono }}>
                        ({prov.base_url})
                      </span>
                    )}
                  </div>
                  {isDefault && (
                    <span
                      style={{
                        fontSize: 10,
                        textTransform: "uppercase",
                        letterSpacing: "0.08em",
                        color: "var(--accent, #6b4f8a)",
                        fontWeight: 600,
                        fontFamily: tokens.ffMono,
                      }}
                    >
                      {t("admin:config.default")}
                    </span>
                  )}
                </div>
              );
            })
          ) : (
            <div style={readonlyVal}>—</div>
          )}
        </div>
      </div>

      <div style={row}>
        <label style={label}>{t("admin:config.default_model")}</label>
        <select
          style={inputBase}
          value={draft.default_model}
          onChange={(e) => set("default_model", e.target.value)}
        >
          <option value="">—</option>
          {(modelOptionsByProvider[draft.default_provider] || []).map((m) => (
            <option key={m} value={m}>{m}</option>
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
