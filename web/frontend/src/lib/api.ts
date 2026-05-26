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
