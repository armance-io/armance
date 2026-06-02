"use client";

import {
  type CSSProperties,
  type FC,
  useState,
  useEffect,
  useCallback,
} from "react";
import { useQuery } from "@tanstack/react-query";
import { useLatestSession } from "@/lib/useLatestSession";
import { tokens } from "../_shared/armance-tokens";
import { PulseDot } from "../_shared/PulseDot";
import { ConfigForm, type ConfigValues } from "./ConfigForm";
import { SecretsList, type SecretEntry } from "./SecretsList";
import { LogViewer, type LogEntry } from "./LogViewer";
import { LogLevelToggle } from "./LogLevelToggle";
import { StatsDashboard, type AgentStat } from "./StatsDashboard";
import { AgentEditor, type AgentRecord } from "./AgentEditor";
import { FootprintTab } from "./FootprintTab";
import { useFootprint, getFootprint } from "@/lib/footprint";
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
  const { sid } = useLatestSession();
  const [activeTab, setActiveTab] = useState<Tab>("config");

  const isLogs = activeTab === "logs";

  // BUG-06: uniform tab content rhythm via shared tokens (not magic numbers).
  // Flex column bounded by <main> (definite height) so a tab can hand its child
  // a real height to scroll inside: the Logs tab fills it (filter bar pinned,
  // rows scroll); other tabs scroll within the tabpanel.
  const outer: CSSProperties = {
    fontFamily: tokens.ffSans,
    color: tokens.ink,
    padding: `${tokens.tabPadY} ${tokens.tabPadX}`,
    maxWidth: 900,
    marginInline: "auto",
    ...(isLogs ? {
      height: "100%",
      minHeight: 0,
      display: "flex",
      flexDirection: "column",
    } : {}),
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

      <div role="tabpanel" style={isLogs ? { flex: 1, minHeight: 0, overflowY: "auto" } : {}}>
        {activeTab === "config" && <ConfigTab pid={pid} t={t} />}
        {activeTab === "secrets" && <SecretsTab pid={pid} t={t} />}
        {activeTab === "logs" && <LogsTab pid={pid} t={t} />}
        {activeTab === "stats" && <StatsTab pid={pid} t={t} />}
        {activeTab === "agents" && <AgentsTab pid={pid} sid={sid} t={t} />}
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
  const [providerOptions, setProviderOptions] = useState<string[]>([]);

  useEffect(() => {
    void Promise.all([getAdminConfig(pid), getProviders()]).then(([raw, prov]) => {
      setCfg({
        default_provider: String(raw.default_provider ?? ""),
        default_model: String(raw.default_model ?? ""),
        budget_effort: (raw.budget_effort as ConfigValues["budget_effort"]) ?? "free-first",
        language: String(raw.language ?? "en"),
        providers: (raw.providers as ConfigValues["providers"]) ?? [],
      });
      const provs = (prov.providers ?? {}) as Record<string, Array<{ id?: string }>>;
      setProviderOptions(Object.keys(provs).sort());
    });
  }, [pid]);

  const onAddProviderSecrets = async (provName: string, apiKey: string, baseUrl?: string) => {
    const provUpper = provName.toUpperCase().replace("-", "_");
    if (apiKey) {
      await putAdminSecret(pid, `${provUpper}_API_KEY`, apiKey);
    }
    if (baseUrl) {
      await putAdminSecret(pid, `${provUpper}_BASE_URL`, baseUrl);
    }
  };

  const onSave = async (values: ConfigValues) => {
    const currentProvs = cfg?.providers ?? [];
    const nextProvs = values.providers ?? [];
    const deletedProvs = currentProvs.filter((cp) => !nextProvs.some((np) => np.name === cp.name));

    for (const dp of deletedProvs) {
      const provUpper = dp.name.toUpperCase().replace("-", "_");
      try {
        await deleteAdminSecret(pid, `${provUpper}_API_KEY`);
      } catch (e) {
        console.warn(`Could not delete API key for ${dp.name}`, e);
      }
      try {
        await deleteAdminSecret(pid, `${provUpper}_BASE_URL`);
      } catch (e) {
        console.warn(`Could not delete BASE_URL for ${dp.name}`, e);
      }
    }

    const updated = await patchAdminConfig(pid, values as unknown as Record<string, unknown>);
    setCfg({
      default_provider: String(updated.default_provider ?? ""),
      default_model: String(updated.default_model ?? ""),
      budget_effort: (updated.budget_effort as ConfigValues["budget_effort"]) ?? "free-first",
      language: String(updated.language ?? "en"),
      providers: (updated.providers as ConfigValues["providers"]) ?? [],
    });
  };

  if (!cfg) return null;
  return (
    <div data-testid="config-form">
      <ConfigForm
        values={cfg}
        providerOptions={providerOptions}
        languageOptions={["en", "fr"]}
        onSave={onSave}
        onAddProviderSecrets={onAddProviderSecrets}
        t={t}
      />
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
  const onReveal = async (key: string) => {
    const data = await getAdminSecrets(pid, true);
    const found = data.find((s) => s.name === key);
    return found ? found.value : "";
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
      <SecretsList secrets={secrets} onEdit={onEdit} onDelete={onDelete} onReveal={onReveal} t={t} />
    </div>
  );
};

// ---------------------------------------------------------------------------
// Logs tab
// ---------------------------------------------------------------------------

function logLineToEntry(l: import("@/lib/api").LogLine, id: string): LogEntry {
  return {
    id,
    ts: l.timestamp || "",
    agent: l.agent || "System",
    level: "info" as LogEntry["level"],
    message: l.event
      ? `${String(l.event).toUpperCase()} — ${l.tokens_in ?? 0} In / ${l.tokens_out ?? 0} Out ($${(l.cost_usd ?? 0).toFixed(4)})`
      : JSON.stringify(l),
    payload: l,
  };
}

const LogsTab: FC<{ pid: string; t: (k: string) => string }> = ({ pid, t }) => {
  const [extra, setExtra] = useState<LogEntry[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [logLevel, setLogLevel] = useState<"INFO" | "DEBUG" | "WARN" | "ERROR">("INFO");

  // BUG-11: live tail — poll the first page every 2s so new logs appear
  // without a manual refresh.
  const { data: head } = useQuery({
    queryKey: ["admin-logs", pid],
    queryFn: () => getAdminLogs(pid, { limit: 50 }),
    refetchInterval: 2000,
  });

  useEffect(() => {
    setCursor(head?.cursor ?? null);
    setExtra([]); // older pages reset when the live head refreshes
  }, [head?.cursor]);

  const headEntries = (head?.lines ?? []).map((l, i) => logLineToEntry(l, `head-${i}`));
  const entries = [...headEntries, ...extra];

  const loadMore = async () => {
    if (!cursor) return;
    const res = await getAdminLogs(pid, { limit: 50, cursor });
    setExtra((prev) => [...prev, ...res.lines.map((l, i) => logLineToEntry(l, `more-${prev.length + i}`))]);
    setCursor(res.cursor);
  };

  return (
    <div
      data-testid="log-viewer"
      style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12, flexShrink: 0 }}>
        <LogLevelToggle
          current={logLevel}
          onChange={async (lvl) => { await patchLogLevel(pid, lvl); setLogLevel(lvl); }}
          t={t}
        />
        <span
          data-testid="logs-live-badge"
          style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            fontFamily: tokens.ffMono, fontSize: 11, color: tokens.inkSoft,
          }}
        >
          <PulseDot />
          {t("admin:logs.live")}
        </span>
      </div>
      <div style={{ flex: 1, minHeight: 0 }}>
        <LogViewer entries={entries} agents={[]} loadMore={loadMore} hasMore={cursor !== null} t={t} />
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Stats tab
// ---------------------------------------------------------------------------

const StatsTab: FC<{ pid: string; t: (k: string) => string }> = ({ pid, t }) => {
  const [agents, setAgents] = useState<AgentStat[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    void Promise.all([
      getAdminStats(pid),
      getFootprint(pid, "agent").catch(() => null),
    ]).then(([statsData, footprintData]) => {
      const statsMap = statsData?.agents ?? {};
      const footprintMap = footprintData?.by_agent ?? {};

      const allAgentNames = Array.from(
        new Set([...Object.keys(statsMap), ...Object.keys(footprintMap)]),
      );

      const merged: AgentStat[] = allAgentNames.map((name) => {
        const s = statsMap[name] ?? { tokens_in: 0, tokens_out: 0, cost_usd: 0, msg_count: 0 };
        const f = footprintMap[name] ?? { gco2e: 0, water_ml: 0, has_estimate: false };
        return {
          agent: name,
          tokens_in: s.tokens_in,
          tokens_out: s.tokens_out,
          cost: s.cost_usd,
          messages: s.msg_count,
          gco2e: f.gco2e,
          water_ml: f.water_ml,
          has_estimate: f.has_estimate,
        };
      });

      setAgents(merged);
      setLoading(false);
    }).catch((err) => {
      console.error(err);
      setLoading(false);
    });
  }, [pid]);

  if (loading) {
    return <div style={{ padding: 20, color: tokens.inkSoft, fontFamily: tokens.ffSans }}>{t("app:loading")}</div>;
  }

  return (
    <div data-testid="stats-dashboard">
      <StatsDashboard agents={agents} t={t} />
    </div>
  );
};

// ---------------------------------------------------------------------------
// Agents tab
// ---------------------------------------------------------------------------

const AgentsTab: FC<{ pid: string; sid: string | null; t: (k: string) => string }> = ({ pid, sid, t }) => {
  const [agentRecords, setAgentRecords] = useState<AgentRecord[]>([]);
  const [providers, setProviders] = useState<string[]>([]);
  const [modelOptionsByProvider, setModelOptionsByProvider] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!sid) return;
    setLoading(true);
    void Promise.all([getAdminAgents(pid, sid), getProviders()]).then(
      ([agts, prov]) => {
        setAgentRecords(
          agts.map((a) => ({
            // id holds the file slug — PATCH targets the slug, not the
            // friendly display name (staff names are labels like "Armance").
            id: a.slug ?? a.name,
            name: a.name,
            role: a.role,
            persona: a.persona ?? "",
            portraitUrl: "",
            provider: a.provider,
            model: a.model,
            reasoning: (a.reasoning as AgentRecord["reasoning"]) ?? "off",
            supportsReasoning: false,
          })),
        );
        const provs = (prov.providers ?? {}) as Record<string, Array<{ id?: string }>>;
        setProviders(Object.keys(provs).sort());

        const mapped: Record<string, string[]> = {};
        for (const [pName, mList] of Object.entries(provs)) {
          mapped[pName] = mList.map((m) => m.id ?? "").filter(Boolean).sort();
        }
        setModelOptionsByProvider(mapped);
      },
    ).catch(console.error).finally(() => setLoading(false));
  }, [pid, sid]);

  const onSave = async (agent: AgentRecord) => {
    if (!sid) return;
    await patchAdminAgent(pid, sid, agent.id, {
      provider: agent.provider,
      model: agent.model,
      reasoning: agent.reasoning ?? null,
    });
  };

  if (!sid) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: tokens.inkSoft, fontFamily: tokens.ffSans }}>
        <p style={{ fontSize: 16, marginBottom: 12, fontWeight: 500 }}>{t("visual:empty.session.title")}</p>
        <p style={{ fontSize: 13 }}>{t("visual:empty.session.hint")}</p>
      </div>
    );
  }

  if (loading) {
    return <div style={{ padding: 40, color: tokens.inkSoft, fontFamily: tokens.ffSans }}>{t("app:loading")}</div>;
  }

  return (
    <div data-testid="agent-editor">
      <AgentEditor
        agents={agentRecords}
        providerOptions={providers}
        modelOptionsByProvider={modelOptionsByProvider}
        onSave={onSave}
        t={t}
      />
    </div>
  );
};

export default AdminPageContainer;
