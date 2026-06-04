import { type CSSProperties, type FC } from "react";
import { tokens } from "../_shared/armance-tokens";
import { providerLabel } from "@/lib/providerLabels";
import { EMBEDDING_PROVIDERS } from "@/lib/embeddingProviders";
import type { EmbeddingModel } from "@/lib/api";

export interface EmbeddingSectionProps {
  /** Currently selected embedding provider. */
  provider: string;
  /** Currently selected embedding model id (free-text allowed). */
  value: string;
  /** Cross-provider embedding catalogue for the type-ahead list. */
  options: EmbeddingModel[];
  onChange: (provider: string, model: string) => void;
  t: (key: string) => string;
}

/**
 * Embedding-model picker for the admin Configuration form. Extracted from
 * ConfigForm (which is already over the component-size cap). Type-ahead
 * over the discovered cross-provider catalogue, but free-text is allowed
 * so any model id can be entered.
 */
export const EmbeddingSection: FC<EmbeddingSectionProps> = ({ provider, value, options, onChange, t }) => {
  const row: CSSProperties = { display: "grid", gap: 6, marginBottom: 20 };
  const label: CSSProperties = {
    fontSize: 12,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: tokens.inkSoft,
    fontFamily: tokens.ffMono,
  };
  const input: CSSProperties = {
    padding: "10px 12px",
    border: `1px solid ${tokens.rule}`,
    background: tokens.bgPaper,
    fontFamily: tokens.ffMono,
    fontSize: 13,
    color: tokens.ink,
  };

  const effectiveProvider = provider || EMBEDDING_PROVIDERS[0] || "";

  const handleModel = (id: string) => {
    // Auto-sync provider when the typed id matches a catalogue entry, else
    // keep the explicitly chosen provider so it is never left empty.
    const match = options.find((o) => o.id === id);
    onChange(match?.provider ?? effectiveProvider, id);
  };

  return (
    <div style={row}>
      <label style={label}>{t("admin:config.embedding")}</label>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 8 }}>
        <select
          value={effectiveProvider}
          onChange={(e) => onChange(e.target.value, value)}
          style={input}
        >
          {EMBEDDING_PROVIDERS.map((p) => (
            <option key={p} value={p}>{providerLabel(p)}</option>
          ))}
        </select>
        <input
          list="admin-embedding-list"
          value={value}
          onChange={(e) => handleModel(e.target.value)}
          placeholder={t("admin:config.embedding_placeholder")}
          style={input}
        />
      </div>
      <datalist id="admin-embedding-list">
        {options.map((m) => (
          <option key={`${m.provider}:${m.id}`} value={m.id}>
            {`${providerLabel(m.provider)} — ${m.name}`}
          </option>
        ))}
      </datalist>
      <span style={{ fontSize: 12, color: tokens.inkFaint, fontStyle: "italic" }}>
        {t("admin:config.embedding_hint")}
      </span>
    </div>
  );
};

export default EmbeddingSection;
