"use client";

import {
  type CSSProperties,
  type FC,
  useState,
  useEffect,
  useCallback,
  useMemo,
} from "react";
import { useQuery } from "@tanstack/react-query";
import { useLatestSession } from "@/lib/useLatestSession";
import { tokens } from "../_shared/armance-tokens";
import { PulseDot } from "../_shared/PulseDot";
import { ConfigForm, type ConfigValues } from "./ConfigForm";

import { LogViewer, type LogEntry } from "./LogViewer";
import { LogLevelToggle } from "./LogLevelToggle";
import { StatsDashboard, type AgentStat } from "./StatsDashboard";
import { AgentEditor, type AgentRecord } from "./AgentEditor";
import { getFootprint } from "@/lib/footprint";
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
  getEmbeddingModels,
  type EmbeddingModel,
} from "@/lib/api";
import { KNOWN_PROVIDERS } from "@/lib/providerLabels";

type Tab = "config" | "logs" | "stats" | "agents";
const TABS: Tab[] = ["config", "logs", "stats", "agents"];

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

      <div role="tabpanel" style={isLogs ? { flex: 1, minHeight: 0, display: "flex", flexDirection: "column" } : {}}>
        {activeTab === "config" && <ConfigTab pid={pid} t={t} />}
        {activeTab === "logs" && <LogsTab pid={pid} t={t} />}
        {activeTab === "stats" && <StatsTab pid={pid} t={t} />}
        {activeTab === "agents" && <AgentsTab pid={pid} sid={sid} t={t} />}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Config tab
// ---------------------------------------------------------------------------

const ConfigTab: FC<{ pid: string; t: (k: string) => string }> = ({ pid, t }) => {
  const [cfg, setCfg] = useState<ConfigValues | null>(null);
  const [providerOptions, setProviderOptions] = useState<string[]>([]);
  const [embeddingOptions, setEmbeddingOptions] = useState<EmbeddingModel[]>([]);
  const [secrets, setSecrets] = useState<Array<{ name: string; value: string; set: boolean }>>([]);

  const reloadSecrets = useCallback(() => {
    void getAdminSecrets(pid, true)
      .then((data) => {
        setSecrets(
          data.map((s) => ({
            name: s.name,
            value: s.value,
            set: s.set,
          }))
        );
      })
      .catch(console.error);
  }, [pid]);

  useEffect(() => {
    void Promise.all([getAdminConfig(pid), getProviders()]).then(([raw, prov]) => {
      setCfg({
        default_provider: String(raw.default_provider ?? ""),
        default_model: String(raw.default_model ?? ""),
        budget_effort: (raw.budget_effort as ConfigValues["budget_effort"]) ?? "free-first",
        language: String(raw.language ?? "en"),
        embedding_provider: String(raw.embedding_provider ?? ""),
        embedding_model: String(raw.embedding_model ?? ""),
        providers: (raw.providers as ConfigValues["providers"]) ?? [],
      });
      const provs = (prov.providers ?? {}) as Record<string, Array<{ id?: string }>>;
      // The "add provider" picker must offer every supported provider, not
      // only the ones discovery returned (which are the already-configured
      // ones). Union the canonical set with whatever discovery surfaced.
      setProviderOptions(
        Array.from(new Set([...KNOWN_PROVIDERS, ...Object.keys(provs)])).sort(),
      );
    });
    void getEmbeddingModels()
      .then((res) => setEmbeddingOptions(res.models ?? []))
      .catch(console.error);
    reloadSecrets();
  }, [pid, reloadSecrets]);

  const onAddProviderSecrets = async (provName: string, apiKey: string, baseUrl?: string) => {
    const provUpper = provName.toUpperCase().replace("-", "_");
    if (apiKey) {
      await putAdminSecret(pid, `${provUpper}_API_KEY`, apiKey);
    }
    if (baseUrl) {
      await putAdminSecret(pid, `${provUpper}_BASE_URL`, baseUrl);
    }
    reloadSecrets();
  };

  const onEditSecret = async (key: string, val: string) => {
    await putAdminSecret(pid, key, val);
    reloadSecrets();
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
      embedding_provider: String(updated.embedding_provider ?? ""),
      embedding_model: String(updated.embedding_model ?? ""),
      providers: (updated.providers as ConfigValues["providers"]) ?? [],
    });
    reloadSecrets();
  };

  if (!cfg) return null;
  return (
    <div data-testid="config-form">
      <ConfigForm
        values={cfg}
        providerOptions={providerOptions}
        languageOptions={["en", "fr"]}
        embeddingOptions={embeddingOptions}
        onSave={onSave}
        onAddProviderSecrets={onAddProviderSecrets}
        secrets={secrets}
        onEditSecret={onEditSecret}
        t={t}
      />
    </div>
  );
};

// ---------------------------------------------------------------------------
// Logs tab
// ---------------------------------------------------------------------------

function logLineToEntry(l: import("@/lib/api").LogLine): LogEntry {
  // Use a stable, unique ID based on timestamp, agent, and event to identify duplicates across pages
  const stableId = (l.id as string) || `${l.timestamp || ""}-${l.agent || ""}-${l.event || ""}-${l.tokens_in || 0}-${l.tokens_out || 0}`;
  return {
    id: stableId,
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
  const [allLogs, setAllLogs] = useState<LogEntry[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [logLevel, setLogLevel] = useState<"INFO" | "DEBUG" | "WARN" | "ERROR">("INFO");
  const [loadingMore, setLoadingMore] = useState(false);

  // BUG-11: live tail — poll the first page every 2s so new logs appear at the top.
  const { data: head } = useQuery({
    queryKey: ["admin-logs", pid],
    queryFn: () => getAdminLogs(pid, { limit: 50 }),
    refetchInterval: 2000,
  });

  useEffect(() => {
    if (!head?.lines) return;
    setAllLogs((prev) => {
      const incoming = head.lines.map((l) => logLineToEntry(l));
      // Merge incoming with existing entries and de-duplicate by stable ID
      const seen = new Set<string>();
      const combined = [...incoming, ...prev];
      const deduplicated = combined.filter((item) => {
        if (seen.has(item.id)) return false;
        seen.add(item.id);
        return true;
      });
      // Sort newest-first
      return deduplicated.sort((a, b) => b.ts.localeCompare(a.ts));
    });
    setHasMore((prev) => {
      // If we already reached the end (hasMore was false), keep it false.
      // Otherwise, check if head has a next cursor.
      return prev === false ? false : head.cursor !== null;
    });
  }, [head]);

  const agentsList = useMemo(() => {
    return Array.from(new Set(allLogs.map((l) => l.agent))).sort();
  }, [allLogs]);

  const loadMore = async () => {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    try {
      // Offset equals the total number of unique logs we have loaded so far
      const offset = allLogs.length;
      const res = await getAdminLogs(pid, { limit: 50, cursor: String(offset) });
      const incoming = res.lines.map((l) => logLineToEntry(l));
      
      setAllLogs((prev) => {
        const seen = new Set<string>();
        const combined = [...prev, ...incoming];
        const deduplicated = combined.filter((item) => {
          if (seen.has(item.id)) return false;
          seen.add(item.id);
          return true;
        });
        return deduplicated.sort((a, b) => b.ts.localeCompare(a.ts));
      });
      setHasMore(res.cursor !== null);
    } catch (err) {
      console.error("Failed to load more logs:", err);
    } finally {
      setLoadingMore(false);
    }
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
        <LogViewer entries={allLogs} agents={agentsList} loadMore={loadMore} hasMore={hasMore} t={t} />
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Stats tab
// ---------------------------------------------------------------------------

const StatsTab: FC<{ pid: string; t: (k: string) => string }> = ({ pid, t }) => {
  const { sid } = useLatestSession();
  const [agents, setAgents] = useState<AgentStat[]>([]);
  const [equiv, setEquiv] = useState<import("@/lib/footprint").FootprintEquiv | undefined>(undefined);
  const [dominantZone, setDominantZone] = useState<string | null>(null);
  const [providers, setProviders] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    void Promise.all([
      getAdminStats(pid),
      getFootprint(pid, "agent").catch(() => null),
      sid ? getAdminAgents(pid, sid).catch(() => []) : Promise.resolve([]),
    ]).then(([statsData, footprintData, roster]) => {
      const statsMap = statsData?.agents ?? {};
      const footprintMap = footprintData?.by_agent ?? {};
      setEquiv(footprintData?.equiv);
      setDominantZone(footprintData?.dominant_zone ?? null);
      setProviders(Array.from(new Set(roster.map((a) => a.provider).filter(Boolean))).sort());

      const allAgentNames = Array.from(
        new Set([...Object.keys(statsMap), ...Object.keys(footprintMap)]),
      );

      const merged: AgentStat[] = allAgentNames.map((name) => {
        const s = statsMap[name] ?? { tokens_in: 0, tokens_out: 0, cost_usd: 0, msg_count: 0 };
        const f: Partial<import("@/lib/footprint").FootprintBucket> =
          footprintMap[name] ?? {};
        return {
          agent: name,
          tokens_in: s.tokens_in,
          tokens_out: s.tokens_out,
          cost: s.cost_usd,
          messages: s.msg_count,
          gco2e: f.gco2e ?? 0,
          water_ml: f.water_ml ?? 0,
          has_estimate: f.has_estimate ?? false,
          gco2e_min: f.gco2e_min,
          gco2e_max: f.gco2e_max,
          water_ml_min: f.water_ml_min,
          water_ml_max: f.water_ml_max,
        } satisfies AgentStat;
      });

      setAgents(merged);
      setLoading(false);
    }).catch((err) => {
      console.error(err);
      setLoading(false);
    });
  }, [pid, sid]);

  if (loading) {
    return <div style={{ padding: 20, color: tokens.inkSoft, fontFamily: tokens.ffSans }}>{t("app:loading")}</div>;
  }

  return (
    <div data-testid="stats-dashboard">
      <StatsDashboard agents={agents} equiv={equiv} dominantZone={dominantZone} providers={providers} t={t} />
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

  const [reasoningSet, setReasoningSet] = useState<Set<string>>(new Set());

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
            staff: a.staff ?? false,
            boostProvider: a.boost_provider ?? "",
            boostModel: a.boost_model ?? "",
            boostReasoning: (a.boost_reasoning as AgentRecord["boostReasoning"]) ?? "off",
          })),
        );
        const provs = (prov.providers ?? {}) as Record<string, Array<{ id?: string; supports_reasoning?: boolean }>>;
        setProviders(Object.keys(provs).sort());

        const mapped: Record<string, string[]> = {};
        const rset = new Set<string>();
        for (const [pName, mList] of Object.entries(provs)) {
          mapped[pName] = mList.map((m) => m.id ?? "").filter(Boolean).sort();
          for (const m of mList) {
            if (m.supports_reasoning && m.id) rset.add(`${pName}::${m.id}`);
          }
        }
        setModelOptionsByProvider(mapped);
        setReasoningSet(rset);
      },
    ).catch(console.error).finally(() => setLoading(false));
  }, [pid, sid]);

  const reasoningSupported = useCallback(
    (provider: string, model: string) => reasoningSet.has(`${provider}::${model}`),
    [reasoningSet],
  );

  const onSave = async (agent: AgentRecord) => {
    if (!sid) return;
    await patchAdminAgent(pid, sid, agent.id, {
      provider: agent.provider,
      model: agent.model,
      reasoning: agent.reasoning ?? null,
      boost_provider: agent.boostProvider || null,
      boost_model: agent.boostModel || null,
      boost_reasoning: agent.boostModel ? (agent.boostReasoning ?? null) : null,
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
        reasoningSupported={reasoningSupported}
        onSave={onSave}
        t={t}
      />
    </div>
  );
};

export default AdminPageContainer;
