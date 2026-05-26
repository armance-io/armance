import { type CSSProperties, type FC, useState } from "react";
import { tokens } from "../_shared/armance-tokens";

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
      <div>
        <img
          src={draft.portraitUrl}
          alt={draft.name}
          style={{
            width: 96,
            height: 96,
            objectFit: "cover",
            border: `1px solid ${tokens.rule}`,
            borderRadius: 4,
          }}
        />
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
              try {
                await onSave(draft);
              } finally {
                setSaving(false);
              }
            }}
            style={{
              padding: "8px 20px",
              borderRadius: 999,
              border: `1px solid ${tokens.accent}`,
              background: tokens.accent,
              color: tokens.bgPaperCard,
              fontFamily: tokens.ffSans,
              fontSize: 13,
              cursor: saving ? "wait" : "pointer",
            }}
          >
            {saving ? t("admin:agents.saving") : t("admin:agents.save")}
          </button>
        </div>
      </div>
    </div>
  );
};

export default AgentEditor;
