import { type CSSProperties, type FC, useState } from "react";
import { tokens } from "../_shared/armance-tokens";
import { AgentPortrait } from "../visual/AgentPortrait";

export interface AgentRecord {
  id: string;
  name: string;
  role: string;
  persona: string;
  portraitUrl: string;
  provider: string;
  model: string;
  reasoning?: "off" | "low" | "high";
  supportsReasoning: boolean;
}

export interface AgentEditorProps {
  agents: AgentRecord[];
  providerOptions: string[];
  modelOptionsByProvider: Record<string, string[]>;
  onSave: (agent: AgentRecord) => Promise<void>;
  t: (key: string) => string;
}

export const AgentEditor: FC<AgentEditorProps> = ({
  agents,
  providerOptions,
  modelOptionsByProvider,
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
  onSave: (a: AgentRecord) => Promise<void>;
  t: (key: string) => string;
}> = ({ agent, providerOptions, modelOptionsByProvider, onSave, t }) => {
  const [draft, setDraft] = useState<AgentRecord>(agent);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const card: CSSProperties = {
    display: "grid",
    gridTemplateColumns: "120px 1fr",
    gap: 24,
    padding: 24,
    background: tokens.bgPaperCard,
    border: `1px solid ${tokens.rule}`,
    fontFamily: tokens.ffSans,
    color: tokens.ink,
  };
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
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
        <AgentPortrait
          name={draft.name}
          src={draft.portraitUrl}
          tint="#6b4f8a"
          size="md"
        />
        <span style={{ fontSize: 11, fontFamily: tokens.ffMono, color: tokens.inkFaint }}>
          ID: {draft.id}
        </span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div>
          <h3
            style={{
              fontFamily: tokens.ffSerif,
              fontSize: 26,
              margin: 0,
              letterSpacing: "-0.01em",
            }}
          >
            {draft.name}
          </h3>
          <p style={{ ...ro, margin: "4px 0 0", fontStyle: "italic" }}>{draft.role}</p>
        </div>

        <div>
          <span style={label}>{t("admin:agents.persona")}</span>
          <p style={{ ...ro, margin: 0, lineHeight: 1.5 }}>
            {draft.persona}
            <span style={{ color: tokens.inkFaint, marginLeft: 8, fontStyle: "italic" }}>
              {t("admin:agents.persona_hint")}
            </span>
          </p>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
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

        {draft.supportsReasoning && (
          <div>
            <span style={label}>{t("admin:agents.reasoning")}</span>
            <div style={{ display: "flex", gap: 8 }}>
              {(["off", "low", "high"] as const).map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setDraft((d) => ({ ...d, reasoning: r }))}
                  style={{
                    padding: "6px 14px",
                    borderRadius: 999,
                    border: `1px solid ${draft.reasoning === r ? tokens.accent : tokens.rule}`,
                    background: draft.reasoning === r ? tokens.accent : "transparent",
                    color: draft.reasoning === r ? tokens.bgPaperCard : tokens.inkSoft,
                    fontFamily: tokens.ffMono,
                    fontSize: 12,
                    cursor: "pointer",
                  }}
                >
                  {t(`admin:agents.reasoning.${r}`)}
                </button>
              ))}
            </div>
          </div>
        )}

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

export default AgentEditor;
