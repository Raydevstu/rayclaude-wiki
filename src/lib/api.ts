export type Health = { status: string; provider: string; auth: string; skills: number; persistence: string; durable: boolean; warning: string | null }
export type Run = { id: string; ts: number; trigger: string; prompt: string; status: string; baseline_cost: number; actual_cost: number }
export type Usage = { spend_today_usd: number; measured_runs: number; baseline_cost_usd: number; actual_cost_usd: number; saved_pct: number | null; by_tier: Array<{ tier: string; calls: number; in_tok: number; out_tok: number; cost: number }>; daily: Array<{ day: string; cost: number; tokens: number }> }
export type Docs = { faq: Array<{ question: string; answer: string }>; documents: Array<{ id: string; path: string; title: string; category: string }> }
export type Skill = { name: string; description: string; triggers: string[]; priority: number }
export type Skills = { skills: Skill[]; errors: Record<string, string> }
export type Job = { name: string; kind: string; spec: string; prompt: string; enabled: boolean }
export type LedgerEntry = { seq: number; ts: string; run_id: string; kind: string; payload: string; hash: string }
export type LedgerVerification = { ok: boolean; entries: number; head: string }
export type Acceptance = { equals?: string; contains_all?: string[]; json_required_keys?: string[] }
export type RunRequest = { prompt: string; mode?: string; tier?: string; max_cost_usd?: number; timeout_s?: number; acceptance?: Acceptance }
export type Verification = { status: 'verified' | 'failed_verification' | 'unverified'; checks: Record<string, unknown> }
export type Task = { task_id: string; status: string; result: { answer?: string; verification?: Verification } | null; error: string; progress: number; timeout_s: number | null; acceptance: Acceptance | null; retry_of: string | null }
export type TaskStart = { task_id: string; status: string; retry_of?: string }
export type Evaluation = { [key: string]: unknown }

let token = sessionStorage.getItem('tier1-api-token') ?? ''
function headers(json = false): HeadersInit { const values: Record<string, string> = {}; if (json) values['Content-Type'] = 'application/json'; if (token) values.Authorization = `Bearer ${token}`; return values }
async function request<T>(path: string, init?: RequestInit): Promise<T> { const response = await fetch(path, { ...init, headers: { ...headers(Boolean(init?.body)), ...init?.headers } }); if (!response.ok) throw new Error(`${response.status} ${response.statusText}`); return response.json() as Promise<T> }
const get = <T>(path: string) => request<T>(path)
const post = <T>(path: string, body: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(body) })
const del = <T>(path: string) => request<T>(path, { method: 'DELETE' })
export const api = {
  setToken(value: string) { token = value.trim(); if (token) sessionStorage.setItem('tier1-api-token', token); else sessionStorage.removeItem('tier1-api-token') }, getToken: () => token,
  health: () => get<Health>('/health'), runs: () => get<Run[]>('/v1/runs'), usage: () => get<Usage>('/v1/usage'), docs: () => get<Docs>('/v1/docs'), skills: () => get<Skills>('/v1/skills'), jobs: () => get<Job[]>('/v1/jobs'), ledger: () => get<LedgerEntry[]>('/v1/ledger'), verifyLedger: () => get<LedgerVerification>('/v1/ledger/verify'), run: (body: RunRequest) => post<Run>('/v1/run', body), evaluate: () => post<Evaluation>('/v1/evaluate', {}),
  startTask: (body: RunRequest) => post<TaskStart>('/v1/tasks', body), task: (id: string) => get<Task>(`/v1/tasks/${id}`), cancelTask: (id: string) => del<{ cancelling: string }>(`/v1/tasks/${id}`), retryTask: (id: string) => post<TaskStart>(`/v1/tasks/${id}/retry`, {}),
}
