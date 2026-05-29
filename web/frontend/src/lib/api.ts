/**
 * Typed fetch wrappers around the FastAPI backend.
 *
 * All paths are relative — Next.js rewrites /api/* to the backend
 * (see next.config.ts).
 */

const BASE = "/api";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export class ApiConflictError extends ApiError {
  constructor(code: string, message: string) {
    super(409, code, message);
    this.name = "ApiConflictError";
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  init?: RequestInit,
): Promise<T> {
  const headers: Record<string, string> = { "content-type": "application/json" };
  const reqInit: RequestInit = {
    method,
    headers: { ...headers, ...(init?.headers as Record<string, string> | undefined) },
    credentials: "include",
    ...init,
  };
  if (body !== undefined) reqInit.body = JSON.stringify(body);
  const res = await fetch(`${BASE}${path}`, reqInit);
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    const code = typeof detail.detail === "string" ? detail.detail : detail.detail?.error ?? "unknown";
    if (res.status === 409) {
      throw new ApiConflictError(String(code), String(code));
    }
    throw new ApiError(res.status, String(code), String(code));
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  del: <T>(path: string, body?: unknown) => request<T>("DELETE", path, body),
  raw: (path: string, init?: RequestInit) => fetch(`${BASE}${path}`, init),
};

export interface SessionCreated {
  id: string;
  project_id: string;
}

export interface SessionState {
  state: Record<string, unknown>;
  agents: Array<{ name: string; first_name: string; title: string }>;
  language: string;
}

export async function createSession(pid: string = "default"): Promise<SessionCreated> {
  return api.post<SessionCreated>(`/projects/${pid}/sessions`);
}

export async function getSession(pid: string, sid: string): Promise<SessionState> {
  return api.get<SessionState>(`/projects/${pid}/sessions/${sid}`);
}

/* ─── Epic C — chat, checkpoint, agents, providers, hypotheses ─────────── */

export interface TurnAck {
  ack: boolean;
}

export async function submitTurn(
  pid: string,
  sid: string,
  text: string,
): Promise<TurnAck> {
  return api.post<TurnAck>(`/projects/${pid}/sessions/${sid}/turn`, { text });
}

export interface CheckpointResolvePayload {
  checkpoint_id: string;
  content: string;
  is_abort?: boolean;
}

export async function resolveCheckpoint(
  pid: string,
  sid: string,
  body: CheckpointResolvePayload,
): Promise<{ resolved: boolean }> {
  return api.post(`/projects/${pid}/sessions/${sid}/checkpoint`, body);
}

export interface AgentDetails {
  name: string;
  role: string;
  persona: string;
  description: string;
  provider: string;
  model: string;
  reasoning: string | null;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number | null;
}

export async function getAgentDetails(
  pid: string,
  sid: string,
  name: string,
): Promise<AgentDetails> {
  return api.get<AgentDetails>(
    `/projects/${pid}/sessions/${sid}/agents/${encodeURIComponent(name)}`,
  );
}

export interface ProvidersCatalogue {
  providers: Record<string, Array<Record<string, unknown>>>;
  hint?: string;
}

export async function getProviders(): Promise<ProvidersCatalogue> {
  return api.get<ProvidersCatalogue>(`/providers`);
}

export interface HypothesisEntry {
  step_id: string;
  text: string;
  language: "fr" | "en";
}

export async function listHypotheses(
  pid: string,
  sid: string,
  workflow: string,
  runId: string,
): Promise<{ hypotheses: HypothesisEntry[] }> {
  return api.get(
    `/projects/${pid}/sessions/${sid}/workflows/${encodeURIComponent(workflow)}` +
      `/runs/${encodeURIComponent(runId)}/hypotheses`,
  );
}

/* ─── Epic B — Library room ──────────────────────────────────────────────── */

export type DocFormat = "pdf" | "docx" | "md" | "txt";
export type DocStatus = "pending" | "indexed" | "loaded";

export interface Doc {
  name: string;
  format: DocFormat;
  status: DocStatus;
  size_bytes: number;
}

export async function getLibrary(
  pid: string,
  sid: string,
): Promise<{ docs: Doc[] }> {
  return api.get<{ docs: Doc[] }>(`/projects/${pid}/sessions/${sid}/library`);
}

export async function importDoc(
  pid: string,
  sid: string,
  file: File,
  autoIndex: boolean = false,
): Promise<{ imported: string }> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("auto_index", String(autoIndex));
  
  const res = await api.raw(`/projects/${pid}/sessions/${sid}/library/docs`, {
    method: "POST",
    body: formData,
    credentials: "include",
  });
  
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    const code = typeof detail.detail === "string" ? detail.detail : detail.detail?.error ?? "unknown";
    throw new ApiError(res.status, String(code), String(code));
  }
  
  return res.json() as Promise<{ imported: string }>;
}

export async function deleteDoc(
  pid: string,
  sid: string,
  name: string,
  confirm: boolean = true,
): Promise<{ deleted: string }> {
  return api.del<{ deleted: string }>(
    `/projects/${pid}/sessions/${sid}/library/docs/${encodeURIComponent(name)}`,
    { confirm },
  );
}

export type RunStatus = "running" | "completed" | "failed" | "cancelled";

export interface RunItem {
  run_id: string;
  status: RunStatus;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  tokens_total: number | null;
}

export async function listRuns(
  pid: string,
  sid: string,
  workflowName: string,
): Promise<RunItem[]> {
  return api.get<RunItem[]>(
    `/projects/${pid}/sessions/${sid}/workflows/${encodeURIComponent(workflowName)}/runs`,
  );
}

export async function loadRun(
  pid: string,
  sid: string,
  workflowName: string,
  runId: string,
): Promise<Record<string, string>> {
  return api.get<Record<string, string>>(
    `/projects/${pid}/sessions/${sid}/workflows/${encodeURIComponent(workflowName)}/runs/${encodeURIComponent(runId)}`,
  );
}

export async function loadStep(
  pid: string,
  sid: string,
  workflowName: string,
  runId: string,
  stepId: string,
): Promise<string> {
  const path = `/projects/${pid}/sessions/${sid}/workflows/${encodeURIComponent(workflowName)}/runs/${encodeURIComponent(runId)}/step/${encodeURIComponent(stepId)}`;
  const res = await api.raw(path, { method: "GET" });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    const code = typeof detail.detail === "string" ? detail.detail : detail.detail?.error ?? "unknown";
    throw new ApiError(res.status, String(code), String(code));
  }
  return res.text();
}

export async function listWorkflows(
  _pid: string,
  _sid: string,
): Promise<never> {
  throw new Error("NotImplemented");
}

export interface Workflow {
  name: string;
  nodes: Array<{ id: string; data: Record<string, unknown> }>;
  edges: Array<{ id: string; source: string; target: string }>;
}

export async function getWorkflow(
  _pid: string,
  _sid: string,
  _name: string,
): Promise<Workflow> {
  throw new Error("NotImplemented");
}

export interface ActiveWorkflow {
  active: null | {
    workflow: string;
    run_id: string;
    manifest_path: string;
  };
}

export async function getActiveWorkflow(
  pid: string,
  sid: string,
): Promise<ActiveWorkflow> {
  return api.get<ActiveWorkflow>(`/projects/${pid}/sessions/${sid}/active-workflow`);
}

export interface RunArgument {
  id: string;
  claim: string;
  status: "retained" | "rejected" | "open";
  proposed_by: string[];
  proposed_in_steps: string[];
  rejected_by?: string;
  rejection_reason?: string;
  sources: string[];
  weight?: number;
}

export interface RunSource {
  id: string;
  kind: "doc" | "user_msg" | "web";
  ref: string;
  label: string;
}

export interface RunHypothesis {
  step_id: string;
  text: string;
  invalidator?: string;
}

export async function getRunArguments(
  _pid: string,
  _sid: string,
  _workflowName: string,
  _runId: string,
): Promise<{ arguments: RunArgument[] }> {
  throw new Error("NotImplemented");
}

export async function getRunSources(
  _pid: string,
  _sid: string,
  _workflowName: string,
  _runId: string,
): Promise<{ sources: RunSource[] }> {
  throw new Error("NotImplemented");
}

export async function getRunHypotheses(
  _pid: string,
  _sid: string,
  _workflowName: string,
  _runId: string,
): Promise<{ hypotheses: RunHypothesis[] }> {
  throw new Error("NotImplemented");
}

export interface RunLaunched {
  run_id: string;
}

export async function launchWorkflow(
  pid: string,
  sid: string,
  name: string,
  body: { mode: "interactive" | "autonomous"; depth: "quick" | "deep" },
): Promise<RunLaunched> {
  return api.post<RunLaunched>(
    `/projects/${pid}/sessions/${sid}/workflows/${encodeURIComponent(name)}/run`,
    body,
  );
}

export async function stopWorkflow(
  pid: string,
  sid: string,
  name: string,
  confirm: boolean = true,
): Promise<{ status: string }> {
  return api.post<{ status: string }>(
    `/projects/${pid}/sessions/${sid}/workflows/${encodeURIComponent(name)}/stop`,
    { confirm },
  );
}

export async function deleteRun(
  pid: string,
  sid: string,
  name: string,
  runId: string,
  confirm: boolean = true,
): Promise<{ deleted: string }> {
  return api.del<{ deleted: string }>(
    `/projects/${pid}/sessions/${sid}/workflows/${encodeURIComponent(name)}/runs/${encodeURIComponent(runId)}`,
    { confirm },
  );
}


