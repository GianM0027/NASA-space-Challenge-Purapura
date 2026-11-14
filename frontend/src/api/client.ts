// ABOUTME: Typed client of the LunarNav REST API (spec IF-4); one function per endpoint
// ABOUTME: Owner: Gian. Types come from the generated contracts.ts, never written by hand

import type {
  AiAnswer,
  EvaluateRequest,
  Evaluation,
  MissionRequirements,
  Site,
  SiteRanking,
  SkyState,
} from './contracts'

/** Per-service origin reported by the backend: "real", "example" or "error: ...". */
export type ModuleStatus = Record<string, string>

async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`${path}: HTTP ${response.status} ${detail.slice(0, 300)}`)
  }
  return (await response.json()) as T
}

export const api = {
  modules: () => request<ModuleStatus>('/api/modules'),
  sites: () => request<Site[]>('/api/sites'),
  sky: (timeUtc: string) => request<SkyState>(`/api/sky?time_utc=${encodeURIComponent(timeUtc)}`),
  evaluate: (body: EvaluateRequest) => request<Evaluation>('/api/evaluate', body),
  rank: (body: MissionRequirements) => request<SiteRanking>('/api/rank', body),
  ask: (text: string) => request<AiAnswer>('/api/ai/ask', { text }),
}
