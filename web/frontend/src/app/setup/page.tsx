"use client";

import { useState, useEffect, type CSSProperties } from "react";
import { useTranslation } from "react-i18next";
import { Fleuron } from "@/components/visual/Fleuron";
import { ThemeToggle } from "@/components/visual/ThemeToggle";
import {
  initSetup,
  createSession,
  type SetupInitIn,
} from "@/lib/api";

const PROVIDERS = [
  {
    id: "gemini",
    name: "Google Gemini",
    description: "Highly responsive, massive context windows. Dedicated free tiers per quota.",
    envName: "GEMINI_API_KEY",
    placeholder: "AIzaSy...",
    fallbackModels: [
      { id: "gemini-2.5-flash", display_name: "Gemini 2.5 Flash", context_window: 1000000, tier: "low" },
      { id: "gemini-2.5-pro", display_name: "Gemini 2.5 Pro", context_window: 2000000, tier: "medium" },
    ],
  },
  {
    id: "claude-code",
    name: "Claude Subscription",
    description: "Anthropic Claude Pro/Max subscription model via claude-agent-sdk. No API Key required.",
    envName: "",
    placeholder: "",
    requiresKey: false,
    fallbackModels: [
      { id: "claude-opus-4-7", display_name: "Claude Opus 4.7", context_window: 200000, tier: "high" },
      { id: "claude-sonnet-4-6", display_name: "Claude Sonnet 4.6", context_window: 200000, tier: "medium" },
      { id: "claude-haiku-4-5", display_name: "Claude Haiku 4.5", context_window: 200000, tier: "low" },
    ],
  },
  {
    id: "openrouter",
    name: "OpenRouter",
    description: "Unified gateway. Access hundreds of open & closed models (DeepSeek R1, GPT-4o).",
    envName: "OPENROUTER_API_KEY",
    placeholder: "sk-or-...",
    fallbackModels: [
      { id: "google/gemini-2.5-flash", display_name: "Gemini 2.5 Flash", context_window: 1000000, tier: "low" },
      { id: "anthropic/claude-3.5-sonnet", display_name: "Claude 3.5 Sonnet", context_window: 200000, tier: "medium" },
      { id: "deepseek/deepseek-r1:free", display_name: "DeepSeek R1 (Free)", context_window: 16384, tier: "free" },
      { id: "qwen/qwen-2.5-coder-32b-instruct:free", display_name: "Qwen 2.5 Coder 32B (Free)", context_window: 32768, tier: "free" },
    ],
  },
  {
    id: "custom-openai",
    name: "Custom OpenAI API",
    description: "Connect to a custom local endpoint (e.g. Ollama, Llama.cpp, LM Studio, vLLM).",
    envName: "CUSTOM_OPENAI_API_KEY",
    placeholder: "Key (optional)",
    showBaseUrl: true,
    fallbackModels: [],
  },
];

const BUDGETS = [
  {
    id: "free-first" as const,
    name: "Free First",
    description: "Leverage completely free models and API free quotas first. Zero operational cost.",
  },
  {
    id: "low" as const,
    name: "Low Cost",
    description: "Prioritize fast, highly economical models. Best for fast edits and quick interactions.",
  },
  {
    id: "medium" as const,
    name: "Balanced",
    description: "Perfect sweet spot of intelligence and cost. (Highly Recommended default).",
    recommended: true,
  },
  {
    id: "high" as const,
    name: "Maximum Capability",
    description: "Uses the strongest models in full thinking mode, regardless of prompt cost.",
  },
  {
    id: "adaptive" as const,
    name: "Adaptive Effort",
    description: "Intelligently upgrades/downgrades models and reasoning steps dynamically.",
  },
];

const LANGUAGES = [
  { id: "en" as const, label: "English", emoji: "🇬🇧" },
  { id: "fr" as const, label: "Français", emoji: "🇫🇷" },
  { id: "es" as const, label: "Español", emoji: "🇪🇸" },
  { id: "de" as const, label: "Deutsch", emoji: "🇩🇪" },
  { id: "zh" as const, label: "中文", emoji: "🇨🇳" },
  { id: "ja" as const, label: "日本語", emoji: "🇯🇵" },
];



export default function SetupPage() {
  const { t, i18n } = useTranslation();

  const [step, setStep] = useState(1);
  const [language, setLanguage] = useState<SetupInitIn["language"]>("en");
  const [selectedProviders, setSelectedProviders] = useState<string[]>(["gemini"]);
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [baseUrl, setBaseUrl] = useState("http://localhost:11434/v1");
  const [primaryProvider, setPrimaryProvider] = useState("gemini");
  const [model, setModel] = useState("gemini-2.5-flash");
  const [budget, setBudget] = useState<SetupInitIn["budget"]>("medium");

  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  // Sync language with i18n
  const handleLanguageChange = (lang: SetupInitIn["language"]) => {
    setLanguage(lang);
    void i18n.changeLanguage(lang);
  };

  // Keep primary default provider in sync with selected providers list
  useEffect(() => {
    if (!selectedProviders.includes(primaryProvider)) {
      if (selectedProviders.length > 0 && selectedProviders[0]) {
        setPrimaryProvider(selectedProviders[0]);
      }
    }
  }, [selectedProviders, primaryProvider]);

  // Sync state when primary provider changes
  useEffect(() => {
    const provObj = PROVIDERS.find((p) => p.id === primaryProvider);
    if (provObj && provObj.fallbackModels && provObj.fallbackModels[0]) {
      setModel(provObj.fallbackModels[0].id);
    } else {
      setModel("gpt-4o"); // fallback default for custom-openai
    }
    setErrorMsg("");
  }, [primaryProvider]);

  const handleProviderToggle = (provId: string) => {
    if (selectedProviders.includes(provId)) {
      if (selectedProviders.length > 1) {
        setSelectedProviders((prev) => prev.filter((id) => id !== provId));
      }
    } else {
      setSelectedProviders((prev) => [...prev, provId]);
    }
  };

  const handleNext = () => {
    if (step === 2) {
      // Validate that all selected providers requiring keys have keys input
      const missingKey = selectedProviders.find((pId) => {
        const p = PROVIDERS.find((prov) => prov.id === pId);
        return p && p.requiresKey !== false && p.id !== "custom-openai" && !(apiKeys[pId] || "").trim();
      });
      if (missingKey) {
        setErrorMsg("API Key is required for " + PROVIDERS.find((p) => p.id === missingKey)?.name);
        return;
      }
    }
    setErrorMsg("");
    setStep((s) => Math.min(s + 1, 3));
  };

  const handleBack = () => {
    setErrorMsg("");
    setStep((s) => Math.max(s - 1, 1));
  };

  const handleFinish = async () => {
    setSubmitting(true);
    setErrorMsg("");
    try {
      const payload: SetupInitIn = {
        provider: primaryProvider,
        providers_keys: apiKeys,
        model,
        budget,
        language,
      };
      if (apiKeys[primaryProvider] && apiKeys[primaryProvider].trim()) {
        payload.api_key = apiKeys[primaryProvider].trim();
      }

      await initSetup(payload);
      
      // Setup successful! Create session and redirect.
      const session = await createSession("default");
      window.location.replace(`/projects/default/sessions/${session.id}`);
    } catch (err: unknown) {
      console.error("Setup initialization failed", err);
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(msg || "Failed to initialize workspace. Please check your credentials.");
      setSubmitting(false);
    }
  };



  // Styles
  const containerStyle: CSSProperties = {
    minHeight: "100vh",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    background: "var(--bg-paper)",
    color: "var(--ink)",
    fontFamily: "var(--ff-sans)",
    padding: "24px",
    position: "relative",
    overflow: "hidden",
  };

  const glowStyle: CSSProperties = {
    position: "absolute",
    top: "10%",
    left: "50%",
    transform: "translateX(-50%)",
    width: "600px",
    height: "600px",
    background: "radial-gradient(circle, rgba(107,79,138,0.06) 0%, rgba(0,0,0,0) 70%)",
    pointerEvents: "none",
    zIndex: 0,
  };

  const cardStyle: CSSProperties = {
    width: "100%",
    maxWidth: "580px",
    background: "var(--bg-paper-card)",
    borderRadius: "12px",
    border: "1px solid var(--rule-soft)",
    boxShadow: "var(--shadow-pop)",
    padding: "40px",
    display: "flex",
    flexDirection: "column",
    zIndex: 1,
    backdropFilter: "blur(8px)",
    animation: "armance-pop-in 0.35s cubic-bezier(0.16, 1, 0.3, 1) both",
  };

  const titleStyle: CSSProperties = {
    fontFamily: "var(--ff-serif)",
    fontStyle: "italic",
    fontWeight: 400,
    fontSize: "36px",
    lineHeight: 1.1,
    color: "var(--ink)",
    textAlign: "center",
    margin: "0 0 24px 0",
  };

  const progressContainer: CSSProperties = {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    width: "100%",
    marginBottom: "36px",
    position: "relative",
  };

  const progressTrackContainer: CSSProperties = {
    position: "absolute",
    top: "15px",
    left: "16px",
    right: "16px",
    height: "2px",
    background: "var(--rule-soft)",
    zIndex: 0,
  };

  const progressFillStyle = (currentStep: number): CSSProperties => ({
    width: `${((currentStep - 1) / 2) * 100}%`,
    height: "100%",
    background: "var(--accent)",
    transition: "width 0.30s cubic-bezier(0.16, 1, 0.3, 1)",
  });

  const stepDot = (index: number, active: boolean): CSSProperties => ({
    width: "32px",
    height: "32px",
    borderRadius: "50%",
    background: active ? "var(--accent)" : "var(--bg-paper-card)",
    border: `2px solid ${active ? "var(--accent)" : "var(--rule-soft)"}`,
    color: active ? "var(--bg-paper)" : "var(--ink-soft)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "13px",
    fontWeight: 600,
    zIndex: 1,
    transition: "background 0.2s, border-color 0.2s, color 0.2s",
  });

  const formLabel: CSSProperties = {
    fontSize: "12px",
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    color: "var(--ink-soft)",
    marginBottom: "12px",
  };

  const inputStyle: CSSProperties = {
    width: "100%",
    padding: "12px 14px",
    borderRadius: "6px",
    border: "1px solid var(--rule)",
    background: "var(--bg-paper)",
    fontFamily: "var(--ff-mono)",
    fontSize: "13px",
    color: "var(--ink)",
    outline: "none",
    transition: "border-color 0.2s, box-shadow 0.2s",
  };

  const btnStyle = (disabled = false): CSSProperties => ({
    padding: "10px 24px",
    borderRadius: "999px",
    border: disabled ? "1px solid var(--rule-soft)" : "1px solid var(--accent)",
    background: disabled ? "var(--bg-paper-deep)" : "var(--accent)",
    color: disabled ? "var(--ink-faint)" : "var(--bg-paper)",
    fontFamily: "var(--ff-sans)",
    fontSize: "14px",
    fontWeight: 500,
    cursor: disabled ? "not-allowed" : "pointer",
    transition: "background 0.2s, border-color 0.2s, color 0.2s",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  });

  const textBtnStyle: CSSProperties = {
    padding: "10px 24px",
    borderRadius: "999px",
    border: "1px solid transparent",
    background: "transparent",
    color: "var(--ink-soft)",
    fontFamily: "var(--ff-sans)",
    fontSize: "14px",
    fontWeight: 500,
    cursor: "pointer",
    transition: "color 0.2s",
  };

  const gridStyle: CSSProperties = {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "14px",
    marginBottom: "24px",
  };

  const providerCard = (selected: boolean): CSSProperties => ({
    padding: "18px",
    borderRadius: "8px",
    border: `2px solid ${selected ? "var(--accent)" : "var(--rule-soft)"}`,
    background: selected ? "var(--bg-paper)" : "var(--bg-paper-card)",
    cursor: "pointer",
    transition: "border-color 0.2s, background 0.2s, transform 0.15s ease",
    display: "flex",
    flexDirection: "column",
    alignItems: "start",
  });

  const errorAlert: CSSProperties = {
    padding: "12px 16px",
    background: "rgba(164, 65, 65, 0.08)",
    border: "1px solid var(--danger)",
    borderRadius: "6px",
    color: "var(--danger)",
    fontSize: "13px",
    marginBottom: "20px",
    lineHeight: 1.4,
  };

  return (
    <div style={containerStyle}>
      <div style={glowStyle} />

      {/* Theme Switcher placed fixed in the top right */}
      <div style={{ position: "absolute", top: "24px", right: "24px", zIndex: 10 }}>
        <ThemeToggle t={t} />
      </div>

      <div style={cardStyle}>
        <Fleuron size="sm" />
        <h1 style={titleStyle}>{t("setup:title")}</h1>

        {/* Mathematically constrained progress fill bar */}
        <div style={progressContainer}>
          <div style={progressTrackContainer}>
            <div style={progressFillStyle(step)} />
          </div>
          {[1, 2, 3].map((i) => (
            <div key={i} style={stepDot(i, step >= i)}>
              {i}
            </div>
          ))}
        </div>

        {errorMsg && <div style={errorAlert}>{errorMsg}</div>}

        {/* Step 1: Language selection */}
        {step === 1 && (
          <div style={{ display: "flex", flexDirection: "column" }}>
            <h3 style={formLabel}>{t("setup:step_language")}</h3>
            <div style={{ ...gridStyle, gridTemplateColumns: "1fr 1fr 1fr", gap: "10px" }}>
              {LANGUAGES.map((l) => {
                const selected = language === l.id;
                return (
                  <div
                    key={l.id}
                    onClick={() => handleLanguageChange(l.id)}
                    style={{
                      padding: "16px",
                      borderRadius: "6px",
                      border: `1.5px solid ${selected ? "var(--accent)" : "var(--rule-soft)"}`,
                      background: selected ? "var(--bg-paper)" : "var(--bg-paper-card)",
                      cursor: "pointer",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      justifyContent: "center",
                      transition: "border-color 0.2s, background 0.2s",
                      gap: "6px",
                    }}
                  >
                    <span style={{ fontSize: "24px" }}>{l.emoji}</span>
                    <span style={{ fontSize: "13px", fontWeight: 500 }}>{l.label}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Step 2: Provider selection & key inputs */}
        {step === 2 && (
          <div style={{ display: "flex", flexDirection: "column" }}>
            <h3 style={formLabel}>{t("setup:step_provider")}</h3>
            <p style={{ fontSize: "12px", color: "var(--ink-soft)", marginBottom: "14px" }}>
              Select one or more providers to enable.
            </p>
            <div style={{ ...gridStyle, gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "16px" }}>
              {PROVIDERS.map((p) => {
                const selected = selectedProviders.includes(p.id);
                return (
                  <div
                    key={p.id}
                    onClick={() => handleProviderToggle(p.id)}
                    style={providerCard(selected)}
                  >
                    <span style={{ fontWeight: 600, fontSize: "14px", marginBottom: "4px" }}>
                      {p.name}
                    </span>
                    <span style={{ fontSize: "11px", color: "var(--ink-soft)", lineHeight: 1.35 }}>
                      {p.description}
                    </span>
                  </div>
                );
              })}
            </div>

            <div style={{ maxHeight: "200px", overflowY: "auto", paddingRight: "4px" }}>
              {selectedProviders.map((pId) => {
                const p = PROVIDERS.find((prov) => prov.id === pId);
                if (!p) return null;
                const requiresKey = p.requiresKey !== false;
                const showKey = showKeys[pId] || false;

                if (!requiresKey) {
                  return (
                    <div key={pId} style={{ marginTop: "16px", padding: "14px", border: "1px solid var(--rule-soft)", borderRadius: "6px", background: "var(--bg-paper)" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span style={{ fontSize: "11px", fontWeight: 600, textTransform: "uppercase", color: "var(--accent)" }}>
                          {p.name}
                        </span>
                      </div>
                      <p style={{ fontSize: "11px", color: "var(--ink-soft)", marginTop: "6px", marginBottom: 0 }}>
                        Uses subscription auth via local CLI tools. No API Key required.
                      </p>
                    </div>
                  );
                }

                return (
                  <div key={pId} style={{ marginTop: "16px", padding: "14px", border: "1px solid var(--rule-soft)", borderRadius: "6px", background: "var(--bg-paper)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                      <span style={{ fontSize: "11px", fontWeight: 600, textTransform: "uppercase", color: "var(--accent)" }}>
                        {p.name} Configuration
                      </span>
                    </div>

                    {p.showBaseUrl && (
                      <div style={{ marginBottom: "10px" }}>
                        <label style={{ fontSize: "10px", color: "var(--ink-soft)", display: "block", marginBottom: "4px" }}>
                          Base Endpoint URL
                        </label>
                        <input
                          type="text"
                          value={baseUrl}
                          onChange={(e) => setBaseUrl(e.target.value)}
                          style={{ ...inputStyle, padding: "8px 10px" }}
                        />
                      </div>
                    )}

                    <div>
                      <label style={{ fontSize: "10px", color: "var(--ink-soft)", display: "block", marginBottom: "4px" }}>
                        API Key ({p.envName})
                      </label>
                      <div style={{ display: "flex", gap: "8px" }}>
                        <input
                          type={showKey ? "text" : "password"}
                          placeholder={p.placeholder}
                          value={apiKeys[pId] || ""}
                          onChange={(e) => setApiKeys((prev) => ({ ...prev, [pId]: e.target.value }))}
                          style={{ ...inputStyle, padding: "8px 10px", flex: 1 }}
                        />
                        <button
                          type="button"
                          onClick={() => setShowKeys((prev) => ({ ...prev, [pId]: !showKey }))}
                          style={{
                            padding: "0 12px",
                            background: "var(--bg-paper-deep)",
                            border: "1px solid var(--rule)",
                            borderRadius: "6px",
                            color: "var(--ink-soft)",
                            fontSize: "11px",
                            cursor: "pointer",
                          }}
                        >
                          {showKey ? "Hide" : "Show"}
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Step 3: Budget selection */}
        {step === 3 && (
          <div style={{ display: "flex", flexDirection: "column" }}>
            <h3 style={formLabel}>{t("setup:step_budget")}</h3>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "10px",
                maxHeight: "280px",
                overflowY: "auto",
                paddingRight: "4px",
              }}
            >
              {BUDGETS.map((b) => {
                const selected = budget === b.id;
                return (
                  <div
                    key={b.id}
                    onClick={() => setBudget(b.id)}
                    style={{
                      padding: "12px 16px",
                      borderRadius: "6px",
                      border: `1.5px solid ${selected ? "var(--accent)" : "var(--rule-soft)"}`,
                      background: selected ? "var(--bg-paper)" : "var(--bg-paper-card)",
                      cursor: "pointer",
                      transition: "border-color 0.2s, background 0.2s",
                      display: "flex",
                      flexDirection: "column",
                      position: "relative",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "3px" }}>
                      <span style={{ fontWeight: 600, fontSize: "13px" }}>{b.name}</span>
                      {b.recommended && (
                        <span
                          style={{
                            fontSize: "9px",
                            color: "var(--accent)",
                            background: "rgba(107, 79, 138, 0.12)",
                            padding: "1px 5px",
                            borderRadius: "4px",
                            fontWeight: 600,
                          }}
                        >
                          RECOMMENDED
                        </span>
                      )}
                    </div>
                    <span style={{ fontSize: "11px", color: "var(--ink-soft)", lineHeight: 1.35 }}>
                      {b.description}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Navigation buttons */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            marginTop: "32px",
            borderTop: "1px solid var(--rule-soft)",
            paddingTop: "20px",
          }}
        >
          {step > 1 ? (
            <button type="button" onClick={handleBack} style={textBtnStyle}>
              {t("common:back")}
            </button>
          ) : (
            <div />
          )}

          {step < 3 ? (
            <button type="button" onClick={handleNext} style={btnStyle()}>
              {t("common:next")}
            </button>
          ) : (
            <button
              type="button"
              disabled={submitting}
              onClick={handleFinish}
              style={btnStyle(submitting)}
            >
              {submitting ? "Initializing Workspace..." : "Complete Setup"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
