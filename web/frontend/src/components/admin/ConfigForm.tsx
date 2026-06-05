import { type CSSProperties, type FC, useState } from "react";
import { tokens } from "../_shared/armance-tokens";
import { providerLabel } from "@/lib/providerLabels";
import { ElegantPopup } from "../_shared/ElegantPopup";
import { EmbeddingSection } from "./EmbeddingSection";
import type { EmbeddingModel } from "@/lib/api";

export interface ConfigValues {
  default_provider: string;
  default_model: string;
  budget_effort: "free-first" | "low" | "medium" | "high";
  language: string;
  embedding_provider?: string;
  embedding_model?: string;
  electricity_mix_zone?: string;
  providers?: Array<{ name: string; base_url?: string | null }>;
}

export interface ConfigFormProps {
  values: ConfigValues;
  providerOptions: string[];
  languageOptions: string[];
  embeddingOptions?: EmbeddingModel[];
  /** Carbon-intensity zones for the footprint estimate. */
  zoneOptions?: Array<{ code: string; gco2e_per_kwh: number }>;
  onSave: (values: ConfigValues) => Promise<void>;
  onAddProviderSecrets?: (provName: string, apiKey: string, baseUrl?: string) => Promise<void>;
  secrets?: Array<{ name: string; value: string; set: boolean }>;
  onEditSecret?: (key: string, value: string) => Promise<void>;
  t: (key: string) => string;
}

const BUDGETS = ["free-first", "low", "medium", "high"] as const;

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
}> = ({ label, danger, active, children, onClick }) => (
  <button
    type="button"
    aria-label={label}
    title={label}
    onClick={onClick}
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

export const ConfigForm: FC<ConfigFormProps> = ({
  values,
  providerOptions,
  languageOptions,
  embeddingOptions = [],
  zoneOptions = [],
  onSave,
  onAddProviderSecrets,
  secrets = [],
  onEditSecret,
  t,
}) => {
  const [draft, setDraft] = useState<ConfigValues>(values);
  const [errors, setErrors] = useState<Partial<Record<keyof ConfigValues, string>>>({});
  const [saving, setSaving] = useState(false);

  // States for the add provider form
  const [showAddForm, setShowAddForm] = useState(false);
  const [newProvName, setNewProvName] = useState("");
  const [newBaseUrl, setNewBaseUrl] = useState("");
  const [newApiKey, setNewApiKey] = useState("");

  // States for the secrets management
  const [expandedProviders, setExpandedProviders] = useState<Record<string, boolean>>({});
  const [popupSecret, setPopupSecret] = useState<{ key: string; value: string } | null>(null);
  const [editingSecretKey, setEditingSecretKey] = useState<string | null>(null);
  const [editingSecretValue, setEditingSecretValue] = useState("");

  const toggleExpandProvider = (name: string) => {
    setExpandedProviders((prev) => ({ ...prev, [name]: !prev[name] }));
  };

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

  const renderSecretRow = (secretName: string, secret?: { name: string; value: string; set: boolean }) => {
    const isEditing = editingSecretKey === secretName;
    const isBaseUrl = secretName.endsWith("_BASE_URL");
    const isSet = secret ? secret.set : false;
    const displayedValue = isBaseUrl ? (secret?.value || "") : (isSet ? `sk-***…${secret?.value?.slice(-4) || ""}` : "••••");

    return (
      <div
        key={secretName}
        style={{
          display: "grid",
          gridTemplateColumns: "180px 1fr auto",
          gap: 12,
          alignItems: "center",
          padding: "6px 0",
        }}
      >
        <code style={{ fontFamily: tokens.ffMono, fontSize: 11, color: tokens.inkSoft }}>
          {secretName}
        </code>

        {isEditing ? (
          <input
            autoFocus
            type={isBaseUrl ? "text" : "password"}
            value={editingSecretValue}
            onChange={(e) => setEditingSecretValue(e.target.value)}
            style={{
              padding: "4px 8px",
              border: `1px solid ${tokens.accent}`,
              background: tokens.bgPaperDeep,
              fontFamily: tokens.ffMono,
              fontSize: 12,
              color: tokens.ink,
            }}
          />
        ) : (
          <code
            style={{
              fontFamily: tokens.ffMono,
              fontSize: 12,
              color: isSet ? tokens.ink : tokens.inkFaint,
              textAlign: "left",
              justifySelf: "start",
            }}
          >
            {!isSet ? "(not configured)" : displayedValue}
          </code>
        )}

        <div style={{ display: "flex", gap: 4, justifyContent: "flex-end" }}>
          {isEditing ? (
            <>
              <IconBtn
                label={t("admin:secrets.action.save")}
                onClick={async () => {
                  if (onEditSecret) {
                    await onEditSecret(secretName, editingSecretValue);
                  }
                  setEditingSecretKey(null);
                }}
              >
                ✓
              </IconBtn>
              <IconBtn
                label={t("admin:secrets.action.cancel")}
                onClick={() => setEditingSecretKey(null)}
              >
                ✕
              </IconBtn>
            </>
          ) : (
            <>
              {isSet && !isBaseUrl && (
                <IconBtn
                  label={t("admin:secrets.action.reveal")}
                  onClick={async () => {
                    if (secret) {
                      setPopupSecret({ key: secret.name, value: secret.value });
                    }
                  }}
                  active={popupSecret?.key === secretName}
                >
                  <EyeIcon crossed={popupSecret?.key === secretName} />
                </IconBtn>
              )}
              <IconBtn
                label={t("admin:secrets.action.edit")}
                onClick={() => {
                  setEditingSecretKey(secretName);
                  setEditingSecretValue(secret?.value || "");
                }}
              >
                ✎
              </IconBtn>
            </>
          )}
        </div>
      </div>
    );
  };

  const renderProviderSecrets = (provName: string) => {
    if (provName === "claude-code") {
      return (
        <div style={{ fontSize: 12, color: tokens.inkSoft, fontStyle: "italic" }}>
          Uses subscription authentication via local CLI tools. No API Key required.
        </div>
      );
    }

    const apiKeyName = `${provName.toUpperCase().replace("-", "_")}_API_KEY`;
    const baseUrlName = `${provName.toUpperCase().replace("-", "_")}_BASE_URL`;

    const apiSecret = secrets.find((s) => s.name === apiKeyName);
    const baseSecret = secrets.find((s) => s.name === baseUrlName);

    return (
      <div style={{ display: "grid", gap: 10 }}>
        {renderSecretRow(apiKeyName, apiSecret)}
        {/* Only custom-openai needs a configurable base URL. For the other
            providers the endpoint is a fixed constant — no need to expose it. */}
        {provName === "custom-openai" && renderSecretRow(baseUrlName, baseSecret)}
      </div>
    );
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

      {/* Configured Providers Section */}
      <div style={row}>
        <label style={label}>{t("admin:config.providers")}</label>
        <div style={{ display: "grid", gap: 10 }}>
          {draft.providers && draft.providers.length > 0 ? (
            draft.providers.map((prov) => {
              const expanded = expandedProviders[prov.name] || false;
              return (
                <div
                  key={prov.name}
                  style={{
                    border: `1px solid ${tokens.rule}`,
                    background: tokens.bgPaperDeep,
                    borderRadius: "4px",
                    overflow: "hidden",
                    display: "flex",
                    flexDirection: "column",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      padding: "12px 16px",
                      background: tokens.bgPaperCard,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center" }}>
                      <button
                        type="button"
                        onClick={() => toggleExpandProvider(prov.name)}
                        style={{
                          background: "transparent",
                          border: "none",
                          cursor: "pointer",
                          color: tokens.inkSoft,
                          padding: "0 8px 0 0",
                          fontSize: 14,
                          display: "inline-flex",
                          alignItems: "center",
                          transform: "translateY(-1px)",
                        }}
                      >
                        {expanded ? "▾" : "▸"}
                      </button>
                      <span style={{ fontWeight: 600, fontFamily: tokens.ffSans, color: tokens.ink }}>
                        {providerLabel(prov.name)}
                      </span>
                      {prov.base_url && (
                        <span style={{ fontSize: 11, marginLeft: 8, color: tokens.inkSoft, fontFamily: tokens.ffMono }}>
                          ({prov.base_url})
                        </span>
                      )}
                    </div>
                    {draft.providers && draft.providers.length > 1 && (
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
                    )}
                  </div>

                  {expanded && (
                    <div
                      style={{
                        padding: "16px",
                        borderTop: `1px solid ${tokens.rule}`,
                        background: tokens.bgPaper,
                      }}
                    >
                      {renderProviderSecrets(prov.name)}
                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <div style={readonlyVal}>—</div>
          )}
        </div>

        {/* Toggle Button for Add Provider */}
        {availableToAdd.length > 0 && !showAddForm && (
          <div style={{ display: "flex", justifyContent: "flex-start", marginTop: 8 }}>
            <button
              type="button"
              onClick={() => setShowAddForm(true)}
              style={{
                padding: "8px 16px",
                borderRadius: 999,
                border: `1px dashed ${tokens.accent}`,
                background: "transparent",
                color: tokens.accent,
                fontFamily: tokens.ffSans,
                fontSize: 12,
                cursor: "pointer",
                fontWeight: 600,
                transition: "all 0.15s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "color-mix(in srgb, var(--accent) 5%, transparent)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
              }}
            >
              {t("admin:config.add_provider") || "+ Add a Provider"}
            </button>
          </div>
        )}

        {/* Add Provider Selector inline form */}
        {availableToAdd.length > 0 && showAddForm && (
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

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button
                type="button"
                onClick={() => {
                  setShowAddForm(false);
                  setNewProvName("");
                  setNewBaseUrl("");
                  setNewApiKey("");
                }}
                style={{
                  padding: "6px 14px",
                  borderRadius: 4,
                  border: `1px solid ${tokens.rule}`,
                  background: "transparent",
                  color: tokens.inkSoft,
                  fontFamily: tokens.ffSans,
                  fontSize: 12,
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
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

                  setShowAddForm(false);
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

      {/* Carbon-intensity zone — refines the CO₂ estimate to the user's grid. */}
      <div style={row}>
        <label style={label}>{t("admin:config.carbon_zone")}</label>
        <select
          style={inputBase}
          value={draft.electricity_mix_zone ?? "WOR"}
          onChange={(e) => set("electricity_mix_zone", e.target.value)}
        >
          {zoneOptions.map((z) => (
            <option key={z.code} value={z.code}>
              {z.code} · {z.gco2e_per_kwh} gCO₂e/kWh
            </option>
          ))}
        </select>
        <span style={{ color: "var(--ink-faint)", fontSize: 12, fontStyle: "italic" }}>
          {t("admin:config.carbon_zone_hint")}
        </span>
      </div>

      <EmbeddingSection
        provider={draft.embedding_provider ?? ""}
        value={draft.embedding_model ?? ""}
        options={embeddingOptions}
        onChange={(provider, model) =>
          setDraft((d) => ({ ...d, embedding_provider: provider, embedding_model: model }))
        }
        t={t}
      />

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

      {popupSecret && (
        <ElegantPopup
          open={true}
          title={popupSecret.key}
          onClose={() => setPopupSecret(null)}
          cancelLabel={t("common:close") || "Close"}
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
