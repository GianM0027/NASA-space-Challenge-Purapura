// ABOUTME: Typed client of the LunarNav REST API (spec IF-4); one function per endpoint
// ABOUTME: Owner: Gian. Types come from the generated contracts.ts, never written by hand

import type {
  AiAnswer,
  AiRequest,
  EvaluateRequest,
  Evaluation,
  ExplainRequest,
  MissionRequirementsInput,
  Site,
  SiteRanking,
  SkyState,
  UpdateSiteRequest,
} from './contracts'

/** Per-service origin reported by the backend: "real", "example" or "error: ...". */
export type ModuleStatus = Record<string, string>

/** An HTTP error answer: the status code and the backend's `detail` text. */
export class ApiError extends Error {
  readonly status: number
  readonly detail: string

  constructor(path: string, status: number, detail: string) {
    super(`${path}: HTTP ${status} ${detail.slice(0, 300)}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

/** Return FastAPI's `detail` string from an error body, or the raw body when it has none. */
function errorDetail(body: string): string {
  try {
    const parsed: unknown = JSON.parse(body)
    if (parsed && typeof parsed === 'object' && 'detail' in parsed && typeof parsed.detail === 'string') {
      return parsed.detail
    }
  } catch {
    // Not JSON (e.g. a proxy error page): show it as it is.
  }
  return body
}

async function request<T>(path: string, body?: unknown, method?: string): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      method: method ?? (body === undefined ? 'GET' : 'POST'),
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    // fetch rejects only when no HTTP answer arrives at all: the dev servers are not running.
    throw new Error('Backend unreachable: is it running on port 8000 (README, Run)?')
  }
  if (!response.ok) {
    throw new ApiError(path, response.status, errorDetail(await response.text()))
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  modules: () => request<ModuleStatus>('/api/modules'),
  sites: () => request<Site[]>('/api/sites'),
  addSite: (site: Site) => request<Site>('/api/sites', site),
  updateSite: (siteId: string, body: UpdateSiteRequest) =>
    request<Site>(`/api/sites/${encodeURIComponent(siteId)}`, body, 'PATCH'),
  removeSite: (siteId: string) => request<void>(`/api/sites/${encodeURIComponent(siteId)}`, undefined, 'DELETE'),
  sky: (timeUtc: string) => request<SkyState>(`/api/sky?time_utc=${encodeURIComponent(timeUtc)}`),
  evaluate: (body: EvaluateRequest) => request<Evaluation>('/api/evaluate', body),
  rank: (body: MissionRequirementsInput) => request<SiteRanking>('/api/rank', body),
  ask: (body: AiRequest) => request<AiAnswer>('/api/ai/ask', body),
  explain: (body: ExplainRequest) => request<SiteRanking>('/api/ai/explain', body),
}
