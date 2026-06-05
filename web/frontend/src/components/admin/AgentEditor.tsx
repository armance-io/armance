import { type CSSProperties, type FC, useState } from "react";
import { tokens } from "../_shared/armance-tokens";
import { AgentPortrait } from "../visual/AgentPortrait";

export type ReasoningLevel = "off" | "low" | "medium" | "high";
const REASONING_LEVELS: ReasoningLevel[] = ["off", "low", "medium", "high"];

export interface AgentRecord {
  id: string;
  name: string;
  role: string;
  persona: string;
  portraitUrl: string;
  provider: string;
  model: string;
  reasoning?: ReasoningLevel;
  supportsReasoning: boolean;
  staff: boolean;
  // Augment capability — optional stronger fallback model.
  boostProvider?: string;
  boostModel?: string;
  boostReasoning?: ReasoningLevel;
}

export interface AgentEditorProps {
  agents: AgentRecord[];
  providerOptions: string[];
  modelOptionsByProvider: Record<string, string[]>;
  /** (provider, model) → whether reasoning effort is explicitly supported. */
  reasoningSupported?: ((provider: string, model: string) => boolean) | undefined;
  onSave: (agent: AgentRecord) => Promise<void>;
  t: (key: string) => string;
}

export const AgentEditor: FC<AgentEditorProps> = ({
  agents,
  providerOptions,
  modelOptionsByProvider,
  reasoningSupported,
  onSave,
  t,
}) => (
  <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
    {agents.map((a) => (
      <AgentCard
        key={a.id}
        agent={a}
        providerOptions={providerOptions}
        modelOptionsByProvider={modelOptionsByProvider}
        reasoningSupported={reasoningSupported}
        onSave={onSave}
        t={t}
      />
    ))}
  </div>
);

const AgentCard: FC<{
  agent: AgentRecord;
  providerOptions: string[];
  modelOptionsByProvider: Record<string, string[]>;
  reasoningSupported?: ((provider: string, model: string) => boolean) | undefined;
  onSave: (a: AgentRecord) => Promise<void>;
  t: (key: string) => string;
}> = ({ agent, providerOptions, modelOptionsByProvider, reasoningSupported, onSave, t }) => {
  const [draft, setDraft] = useState<AgentRecord>(agent);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const card: CSSProperties = {
    display: "grid",
    gridTemplateColumns: "84px 1fr",
    gap: 18,
    padding: 16,
    background: tokens.bgPaperCard,
    border: `1px solid ${tokens.rule}`,
    fontFamily: tokens.ffSans,
    color: tokens.ink,
  };
  const roleLabel = agent.staff ? t(`roles:${agent.role}`) : agent.role;
  const label: CSSProperties = {
    fontFamily: tokens.ffMono,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: tokens.inkSoft,
    marginBottom: 6,
    display: "block",
  };
  const ro: CSSProperties = {
    color: tokens.inkSoft,
    fontSize: 14,
  };
  const input: CSSProperties = {
    padding: "8px 10px",
    border: `1px solid ${tokens.rule}`,
    background: tokens.bgPaper,
    fontFamily: tokens.ffMono,
    fontSize: 13,
    color: tokens.ink,
    width: "100%",
  };

  return (
    <div style={card}>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
        <AgentPortrait
          name={draft.name}
          src={draft.portraitUrl}
          tint="#6b4f8a"
          size="sm"
        />
        <span style={{ fontSize: 10, fontFamily: tokens.ffMono, color: tokens.inkFaint }}>
          ID: {draft.id}
        </span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
          <h3
            style={{
              fontFamily: tokens.ffSerif,
              fontSize: 20,
              margin: 0,
              letterSpacing: "-0.01em",
            }}
          >
            {draft.name}
          </h3>
          <span style={{ ...ro, fontSize: 13, fontStyle: "italic" }}>{roleLabel}</span>
        </div>

        <div>
          <span style={label}>{t("admin:agents.persona")}</span>
          <p style={{ ...ro, margin: 0, lineHeight: 1.45, fontSize: 13 }}>{draft.persona}</p>
          {!agent.staff && (
            <p style={{ color: tokens.inkFaint, margin: "6px 0 0", fontStyle: "italic", fontSize: 12 }}>
              {t("admin:agents.persona_hint")}
            </p>
          )}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div>
            <span style={label}>{t("admin:agents.provider")}</span>
            <select
              value={draft.provider}
              onChange={(e) =>
                setDraft((d) => ({ ...d, provider: e.target.value, model: "" }))
              }
              style={input}
            >
              {providerOptions.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </div>
          <div>
            <span style={label}>{t("admin:agents.model")}</span>
            <select
              value={draft.model}
              onChange={(e) => setDraft((d) => ({ ...d, model: e.target.value }))}
              style={input}
            >
              <option value="">—</option>
              {(modelOptionsByProvider[draft.provider] || []).map((m) => (
                <option key={m}>{m}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Reasoning — always editable. Some custom-API models support effort
            without advertising it, so we never hide the control; we warn instead. */}
        <ReasoningPicker
          label={t("admin:agents.reasoning")}
          value={draft.reasoning ?? "off"}
          onChange={(r) => setDraft((d) => ({ ...d, reasoning: r }))}
          warn={reasoningSupported ? !reasoningSupported(draft.provider, draft.model) : false}
          t={t}
        />

        {/* Augment capability — optional stronger fallback model the user can
            switch on from the sidebar. */}
        <div style={{ borderTop: `1px solid ${tokens.ruleSoft || tokens.rule}`, paddingTop: 10 }}>
          <span style={label}>{t("admin:agents.augment")}</span>
          <p style={{ color: tokens.inkFaint, margin: "0 0 8px", fontStyle: "italic", fontSize: 12 }}>
            {t("admin:agents.augment_hint")}
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <span style={label}>{t("admin:agents.provider")}</span>
              <select
                value={draft.boostProvider ?? ""}
                onChange={(e) => setDraft((d) => ({ ...d, boostProvider: e.target.value, boostModel: "" }))}
                style={input}
              >
                <option value="">—</option>
                {providerOptions.map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </div>
            <div>
              <span style={label}>{t("admin:agents.model")}</span>
              <select
                value={draft.boostModel ?? ""}
                onChange={(e) => setDraft((d) => ({ ...d, boostModel: e.target.value }))}
                style={input}
              >
                <option value="">—</option>
                {(modelOptionsByProvider[draft.boostProvider ?? ""] || []).map((m) => (
                  <option key={m}>{m}</option>
                ))}
              </select>
            </div>
          </div>
          {draft.boostModel ? (
            <div style={{ marginTop: 10 }}>
              <ReasoningPicker
                label={t("admin:agents.augment_reasoning")}
                value={draft.boostReasoning ?? "off"}
                onChange={(r) => setDraft((d) => ({ ...d, boostReasoning: r }))}
                warn={
                  reasoningSupported
                    ? !reasoningSupported(draft.boostProvider ?? draft.provider, draft.boostModel)
                    : false
                }
                t={t}
              />
            </div>
          ) : null}
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 4 }}>
          <button
            type="button"
            disabled={saving}
            onClick={async () => {
              setSaving(true);
              setSaved(false);
              try {
                await onSave(draft);
                setSaved(true);
                setTimeout(() => setSaved(false), 2000);
              } finally {
                setSaving(false);
              }
            }}
            style={{
              padding: "8px 20px",
              borderRadius: 999,
              border: `1px solid ${saved ? "hsl(120, 15%, 55%)" : tokens.accent}`,
              background: saved ? "hsl(120, 15%, 55%)" : tokens.accent,
              color: tokens.bgPaperCard,
              fontFamily: tokens.ffSans,
              fontSize: 13,
              cursor: saving ? "wait" : "pointer",
              transition: "background 0.25s ease, border-color 0.25s ease",
            }}
          >
            {saving ? (
              t("admin:agents.saving")
            ) : saved ? (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                <svg width="12" height="12" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ display: "block" }}>
                  <path d="M2.5 7.5l3 3 6-7" />
                </svg>
                {t("admin:agents.saved") || "Enregistré"}
              </span>
            ) : (
              t("admin:agents.save")
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

const ReasoningPicker: FC<{
  label: string;
  value: ReasoningLevel;
  onChange: (r: ReasoningLevel) => void;
  warn: boolean;
  t: (key: string) => string;
}> = ({ label, value, onChange, warn, t }) => (
  <div>
    <span
      style={{
        fontFamily: tokens.ffMono, fontSize: 11, textTransform: "uppercase",
        letterSpacing: "0.08em", color: tokens.inkSoft, marginBottom: 6, display: "block",
      }}
    >
      {label}
    </span>
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
      {REASONING_LEVELS.map((r) => (
        <button
          key={r}
          type="button"
          onClick={() => onChange(r)}
          style={{
            padding: "6px 14px",
            borderRadius: 999,
            border: `1px solid ${value === r ? tokens.accent : tokens.rule}`,
            background: value === r ? tokens.accent : "transparent",
            color: value === r ? tokens.bgPaperCard : tokens.inkSoft,
            fontFamily: tokens.ffMono,
            fontSize: 12,
            cursor: "pointer",
          }}
        >
          {t(`admin:agents.reasoning_levels.${r}`)}
        </button>
      ))}
    </div>
    {warn && value !== "off" && (
      <p
        data-testid="reasoning-warning"
        style={{ color: tokens.warning, margin: "6px 0 0", fontSize: 12, fontStyle: "italic" }}
      >
        {t("admin:agents.reasoning_unsupported")}
      </p>
    )}
  </div>
);

export default AgentEditor;
