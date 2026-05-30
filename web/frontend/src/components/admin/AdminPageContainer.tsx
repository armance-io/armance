"use client";

import {
  type CSSProperties,
  type FC,
  useState,
  useEffect,
  useCallback,
} from "react";
import { tokens } from "../_shared/armance-tokens";
import { ConfigForm, type ConfigValues } from "./ConfigForm";
import { SecretsList, type SecretEntry } from "./SecretsList";
import { LogViewer, type LogEntry } from "./LogViewer";
import { LogLevelToggle } from "./LogLevelToggle";
import { StatsDashboard, type AgentStat } from "./StatsDashboard";
import { AgentEditor, type AgentRecord } from "./AgentEditor";
import { FootprintTab } from "./FootprintTab";
import { useFootprint } from "@/lib/footprint";
import {
  getAdminConfig,
  patchAdminConfig,
  getAdminSecrets,
  putAdminSecret,
  deleteAdminSecret,
  getAdminLogs,
  patchLogLevel,
  getAdminStats,
  getAdminAgents,
  patchAdminAgent,
  getProviders,
} from "@/lib/api";

type Tab = "config" | "secrets" | "logs" | "stats" | "agents" | "empreinte";
const TABS: Tab[] = ["config", "secrets", "logs", "stats", "agents", "empreinte"];

interface AdminPageContainerProps {
  pid: string;
  t: (key: string) => string;
}

export const AdminPageContainer: FC<AdminPageContainerProps> = ({ pid, t }) => {
  const [activeTab, setActiveTab] = useState<Tab>("config");

  const outer: CSSProperties = {
    fontFamily: tokens.ffSans,
    color: tokens.ink,
    padding: "32px 40px",
    maxWidth: 900,
  };

  const tabBar: CSSProperties = {
    display: "flex",
    gap: 4,
    borderBottom: `1px solid ${tokens.rule}`,
    marginBottom: 32,
  };

  const tabBtn = (tab: Tab): CSSProperties => ({
    padding: "10px 20px",
    border: "none",
    borderBottom: activeTab === tab ? `2px solid ${tokens.accent}` : "2px solid transparent",
    background: "transparent",
    color: activeTab === tab ? tokens.accent : tokens.inkSoft,
    fontFamily: tokens.ffSans,
    fontSize: 14,
    cursor: "pointer",
    fontWeight: activeTab === tab ? 600 : 400,
  });

  return (
    <div style={outer}>
      <div style={tabBar} role="tablist">
        {TABS.map((tab) => (
          <button
            key={tab}
            role="tab"
            aria-selected={activeTab === tab}
            style={tabBtn(tab)}
            onClick={() => setActiveTab(tab)}
          >
            {t(`admin:tabs.${tab}`)}
          </button>
        ))}
      </div>

      <div role="tabpanel">
        {activeTab === "config" && <ConfigTab pid={pid} t={t} />}
        {activeTab === "secrets" && <SecretsTab pid={pid} t={t} />}
        {activeTab === "logs" && <LogsTab pid={pid} t={t} />}
        {activeTab === "stats" && <StatsTab pid={pid} t={t} />}
        {activeTab === "agents" && <AgentsTab pid={pid} t={t} />}
        {activeTab === "empreinte" && <EmpreinteTab pid={pid} t={t} />}
      </div>
    </div>
  );
};

const EmpreinteTab: FC<{ pid: string; t: (k: string) => string }> = ({ pid, t }) => {
  const { data, loading, error } = useFootprint(pid, "agent");
  return <FootprintTab data={data} loading={loading} error={error} zone="WOR" t={t} />;
};

// ---------------------------------------------------------------------------
// Config tab
// ---------------------------------------------------------------------------

const ConfigTab: FC<{ pid: string; t: (k: string) => string }> = ({ pid, t }) => {
  const [cfg, setCfg] = useState<ConfigValues | null>(null);

  useEffect(() => {
    void getAdminConfig(pid).then((raw) => {
      setCfg({
        default_provider: String(raw.default_provider ?? "openrouter"),
        default_model: String(raw.default_model ?? ""),
        budget_effort: (raw.budget_effort as ConfigValues["budget_effort"]) ?? "free-first",
        language: String(raw.language ?? "en"),
        judge_model: String(raw.judge_model ?? ""),
        log_level: (raw.log_level as ConfigValues["log_level"]) ?? "info",
      });
    });
  }, [pid]);

  const onSave = async (values: ConfigValues) => {
    const updated = await patchAdminConfig(pid, values as unknown as Record<string, unknown>);
    setCfg({
      default_provider: String(updated.default_provider ?? "openrouter"),
      default_model: String(updated.default_model ?? ""),
      budget_effort: (updated.budget_effort as ConfigValues["budget_effort"]) ?? "free-first",
      language: String(updated.language ?? "en"),
      judge_model: String(updated.judge_model ?? ""),
      log_level: (updated.log_level as ConfigValues["log_level"]) ?? "info",
    });
  };

  if (!cfg) return null;
  return (
    <div data-testid="config-form">
      <ConfigForm values={cfg} modelOptions={[]} judgeModelOptions={[]} languageOptions={["en", "fr"]} onSave={onSave} t={t} />
    </div>
  );
};

// ---------------------------------------------------------------------------
// Secrets tab
// ---------------------------------------------------------------------------

const SecretsTab: FC<{ pid: string; t: (k: string) => string }> = ({ pid, t }) => {
  const [secrets, setSecrets] = useState<SecretEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isOnline, setIsOnline] = useState(typeof navigator !== "undefined" ? navigator.onLine : true);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  const reload = useCallback(() => {
    setError(null);
    void getAdminSecrets(pid)
      .then((data) => {
        setSecrets(
          data.map((s) => ({
            key: s.name,
            value: s.value,
            last4: s.value.slice(-4),
          })),
        );
      })
      .catch((err: unknown) => {
        const errorWithStatus = err as { status?: number } | null | undefined;
        if (errorWithStatus && errorWithStatus.status === 403) {
          setError("localhost_only");
        } else {
          setError("fetch_failed");
        }
      });
  }, [pid]);

  const isNonLoopback = typeof window !== "undefined" && !["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
  const showOffline = !isOnline && isNonLoopback;

  useEffect(() => {
    if (showOffline) {
      setError("offline");
      return;
    }
    reload();
  }, [reload, showOffline]);

  const onEdit = async (key: string, newValue: string) => {
    await putAdminSecret(pid, key, newValue);
    reload();
  };
  const onDelete = async (key: string) => {
    await deleteAdminSecret(pid, key);
    reload();
  };

  if (showOffline) {
    return (
      <div style={{ padding: 20, color: tokens.inkSoft, fontFamily: tokens.ffSans }}>
        {t("admin:secrets.offline")}
      </div>
    );
  }

  if (error === "localhost_only") {
    return (
      <div style={{ padding: 20, color: tokens.accent, fontFamily: tokens.ffSans, fontWeight: 500 }}>
        {t("admin:secrets.localhost_only")}
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 20, color: tokens.accent, fontFamily: tokens.ffSans }}>
        {t("admin:secrets.error_loading")}
      </div>
    );
  }

  return (
    <div data-testid="secrets-list">
      <SecretsList secrets={secrets} onEdit={onEdit} onDelete={onDelete} t={t} />
    </div>
  );
};

// ---------------------------------------------------------------------------
// Logs tab
// ---------------------------------------------------------------------------

const LogsTab: FC<{ pid: string; t: (k: string) => string }> = ({ pid, t }) => {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [logLevel, setLogLevel] = useState<"INFO" | "DEBUG" | "WARN" | "ERROR">("INFO");

  useEffect(() => {
    void getAdminLogs(pid, { limit: 50 }).then((res) => {
      setEntries(
        res.lines.map((l, i) => ({
          id: String(i),
          ts: l.timestamp,
          agent: l.agent,
          level: "info" as LogEntry["level"],
          message: JSON.stringify(l),
          payload: l,
        })),
      );
      setCursor(res.cursor);
    });
  }, [pid]);

  const loadMore = async () => {
    if (!cursor) return;
    const res = await getAdminLogs(pid, { limit: 50, cursor });
    setEntries((prev) => [
      ...prev,
      ...res.lines.map((l, i) => ({
        id: `more-${i}`,
        ts: l.timestamp,
        agent: l.agent,
        level: "info" as LogEntry["level"],
        message: JSON.stringify(l),
        payload: l,
      })),
    ]);
    setCursor(res.cursor);
  };

  return (
    <div data-testid="log-viewer">
      <LogLevelToggle
        current={logLevel}
        onChange={async (lvl) => { await patchLogLevel(pid, lvl); setLogLevel(lvl); }}
        t={t}
      />
      <LogViewer entries={entries} agents={[]} loadMore={loadMore} hasMore={cursor !== null} t={t} />
    </div>
  );
};

// ---------------------------------------------------------------------------
// Stats tab
// ---------------------------------------------------------------------------

const StatsTab: FC<{ pid: string; t: (k: string) => string }> = ({ pid, t }) => {
  const [agents, setAgents] = useState<AgentStat[]>([]);

  useEffect(() => {
    void getAdminStats(pid).then((data) => {
      setAgents(
        Object.entries(data.agents).map(([name, s]) => ({
          agent: name,
          tokens_in: s.tokens_in,
          tokens_out: s.tokens_out,
          cost: s.cost_usd,
          messages: s.msg_count,
        })),
      );
    });
  }, [pid]);

  return (
    <div data-testid="stats-dashboard">
      <StatsDashboard agents={agents} t={t} />
    </div>
  );
};

// ---------------------------------------------------------------------------
// Agents tab
// ---------------------------------------------------------------------------

const AgentsTab: FC<{ pid: string; t: (k: string) => string }> = ({ pid, t }) => {
  const [agentRecords, setAgentRecords] = useState<AgentRecord[]>([]);
  const [providers, setProviders] = useState<string[]>([]);

  useEffect(() => {
    const sid = "default";
    void Promise.all([getAdminAgents(pid, sid), getProviders()]).then(
      ([agts, prov]) => {
        setAgentRecords(
          agts.map((a) => ({
            id: a.name,
            name: a.name,
            role: a.role,
            persona: "",
            portraitUrl: "",
            provider: a.provider,
            model: a.model,
            reasoning: (a.reasoning as AgentRecord["reasoning"]) ?? "off",
            supportsReasoning: false,
          })),
        );
        setProviders(Object.keys(prov.providers ?? {}));
      },
    );
  }, [pid]);

  const onSave = async (agent: AgentRecord) => {
    await patchAdminAgent(pid, "default", agent.name, {
      model: agent.model,
      reasoning: agent.reasoning ?? null,
    });
  };

  return (
    <div data-testid="agent-editor">
      <AgentEditor
        agents={agentRecords}
        providerOptions={providers}
        modelOptionsByProvider={{}}
        onSave={onSave}
        t={t}
      />
    </div>
  );
};

export default AdminPageContainer;
