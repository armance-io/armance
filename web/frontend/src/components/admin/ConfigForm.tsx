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
  languageOptions: string[];
  onSave: (values: ConfigValues) => Promise<void>;
  onAddProviderSecrets?: (provName: string, apiKey: string, baseUrl?: string) => Promise<void>;
  t: (key: string) => string;
}

const BUDGETS = ["free-first", "low", "medium", "high"] as const;

export const ConfigForm: FC<ConfigFormProps> = ({
  values,
  providerOptions,
  languageOptions,
  onSave,
  onAddProviderSecrets,
  t,
}) => {
  const [draft, setDraft] = useState<ConfigValues>(values);
  const [errors, setErrors] = useState<Partial<Record<keyof ConfigValues, string>>>({});
  const [saving, setSaving] = useState(false);

  // States for the add provider form
  const [newProvName, setNewProvName] = useState("");
  const [newBaseUrl, setNewBaseUrl] = useState("");
  const [newApiKey, setNewApiKey] = useState("");

  const set = <K extends keyof ConfigValues>(k: K, v: ConfigValues[K]) =>
    setDraft((d) => ({ ...d, [k]: v }));

  const validate = () => {
    const e: Partial<Record<keyof ConfigValues, string>> = {};
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

  const handleDeleteProvider = (name: string) => {
    setDraft((d) => ({
      ...d,
      providers: (d.providers ?? []).filter((p) => p.name !== name),
    }));
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

  const availableToAdd = providerOptions.filter(
    (opt) => !(draft.providers ?? []).some((p) => p.name === opt)
  );

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

      {/* Configured Providers Section */}
      <div style={row}>
        <label style={label}>{t("admin:config.providers")}</label>
        <div style={{ display: "grid", gap: 10 }}>
          {draft.providers && draft.providers.length > 0 ? (
            draft.providers.map((prov) => {
              return (
                <div
                  key={prov.name}
                  style={{
                    ...readonlyVal,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "12px 16px",
                    border: `1px solid ${tokens.rule}`,
                    background: tokens.bgPaperDeep,
                  }}
                >
                  <div>
                    <span style={{ fontWeight: 600, fontFamily: tokens.ffSans, color: tokens.ink }}>
                      {providerLabel(prov.name)}
                    </span>
                    {prov.base_url && (
                      <span style={{ fontSize: 11, marginLeft: 8, color: tokens.inkSoft, fontFamily: tokens.ffMono }}>
                        ({prov.base_url})
                      </span>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDeleteProvider(prov.name)}
                    style={{
                      background: "transparent",
                      border: "none",
                      color: "var(--danger, #a44141)",
                      cursor: "pointer",
                      fontSize: 14,
                      padding: "0 4px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                    title={t("admin:config.delete_provider") || "Delete Provider"}
                  >
                    🗑
                  </button>
                </div>
              );
            })
          ) : (
            <div style={readonlyVal}>—</div>
          )}
        </div>

        {/* Add Provider Selector inline form */}
        {availableToAdd.length > 0 && (
          <div
            style={{
              marginTop: 16,
              padding: 16,
              border: `1px dashed ${tokens.rule}`,
              borderRadius: "4px",
              background: tokens.bgPaperCard,
              display: "flex",
              flexDirection: "column",
              gap: 12,
            }}
          >
            <span style={{ ...label, fontSize: 11 }}>
              {t("admin:config.add_provider") || "+ Add a Provider"}
            </span>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div>
                <label style={{ ...label, fontSize: 9 }}>Select Provider</label>
                <select
                  style={{ ...inputBase, width: "100%" }}
                  value={newProvName}
                  onChange={(e) => {
                    setNewProvName(e.target.value);
                    setNewApiKey("");
                    setNewBaseUrl(e.target.value === "custom-openai" ? "http://localhost:11434/v1" : "");
                  }}
                >
                  <option value="">— Select —</option>
                  {availableToAdd.map((opt) => (
                    <option key={opt} value={opt}>
                      {providerLabel(opt)}
                    </option>
                  ))}
                </select>
              </div>

              {newProvName === "custom-openai" && (
                <div>
                  <label style={{ ...label, fontSize: 9 }}>Base URL</label>
                  <input
                    type="text"
                    value={newBaseUrl}
                    onChange={(e) => setNewBaseUrl(e.target.value)}
                    style={{ ...inputBase, width: "100%" }}
                    placeholder="e.g. http://localhost:11434/v1"
                  />
                </div>
              )}
            </div>

            {newProvName && newProvName !== "claude-code" && (
              <div>
                <label style={{ ...label, fontSize: 9 }}>
                  API Key ({newProvName.toUpperCase().replace("-", "_")}_API_KEY)
                </label>
                <input
                  type="password"
                  value={newApiKey}
                  onChange={(e) => setNewApiKey(e.target.value)}
                  style={{ ...inputBase, width: "100%" }}
                  placeholder="Paste API Key here (will be saved in .env)"
                />
              </div>
            )}

            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button
                type="button"
                disabled={!newProvName}
                onClick={async () => {
                  if (!newProvName) return;
                  
                  if (onAddProviderSecrets) {
                    await onAddProviderSecrets(newProvName, newApiKey, newBaseUrl || undefined);
                  }
                  
                  setDraft((d) => ({
                    ...d,
                    providers: [
                      ...(d.providers ?? []),
                      { name: newProvName, base_url: newBaseUrl || null },
                    ],
                  }));
                  
                  setNewProvName("");
                  setNewBaseUrl("");
                  setNewApiKey("");
                }}
                style={{
                  padding: "6px 14px",
                  borderRadius: 4,
                  border: `1px solid ${tokens.accent}`,
                  background: "transparent",
                  color: tokens.accent,
                  fontFamily: tokens.ffSans,
                  fontSize: 12,
                  cursor: "pointer",
                  fontWeight: 600,
                }}
              >
                + Add Provider
              </button>
            </div>
          </div>
        )}
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
