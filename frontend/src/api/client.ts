// ABOUTME: Typed client of the LunarNav REST API (spec IF-4); one function per endpoint
// ABOUTME: Owner: Gian. Types come from the generated contracts.ts, never written by hand

import type {
  AiAnswer,
  AiRequest,
  CommentAnalysisRequest,
  EvaluateRequest,
  Evaluation,
  ExplainRequest,
  MissionAnalysisRequest,
  MissionRequirementsInput,
  RobustnessReport,
  Site,
  SiteRanking,
  SkyState,
  UpdateSiteRequest,
} from './contracts'
import { aiKeyHeaders } from './aiKey'

/** Per-service origin reported by the backend: "real", "example" or "error: ...". */
export type ModuleStatus = Record<string, string>

/** The server's LLM (GET /api/ai/config): "none" means only a visitor's own key enables the AI. */
export interface AiConfig {
  server_llm: 'cli' | 'api' | 'none' | 'example'
  accepts_user_key: boolean
  key_header: string
}

/** The visitor's account (decision D45): null fields for a guest; null as a whole for nobody. */
export interface AccountInfo {
  username: string | null
  is_guest: boolean
  is_admin: boolean
}

/** A proposal to add a personal site to the shared catalog, with its review outcome. */
export interface ProposalInfo {
  id: number
  username: string
  site: Site
  note: string
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
  decided_at: string | null
  admin_note: string
  community_site_id: string | null
}

/** Edits the admin may make when approving a proposal. */
export interface ApproveBody {
  name?: string | null
  description?: string | null
  sources?: string[]
  admin_note?: string
}

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

async function request<T>(
  path: string,
  body?: unknown,
  method?: string,
  extraHeaders: Record<string, string> = {},
): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      method: method ?? (body === undefined ? 'GET' : 'POST'),
      headers: { ...(body === undefined ? {} : { 'Content-Type': 'application/json' }), ...extraHeaders },
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
  // AI calls carry the visitor's own API key when one is saved (decision D43); no other call does.
  aiConfig: () => request<AiConfig>('/api/ai/config'),
  ask: (body: AiRequest) => request<AiAnswer>('/api/ai/ask', body, undefined, aiKeyHeaders()),
  explain: (body: ExplainRequest) => request<SiteRanking>('/api/ai/explain', body, undefined, aiKeyHeaders()),
  missionAnalysis: (body: MissionAnalysisRequest) => request<RobustnessReport>('/api/mission-analysis', body),
  commentAnalysis: (body: CommentAnalysisRequest) =>
    request<RobustnessReport>('/api/ai/comment-analysis', body, undefined, aiKeyHeaders()),

  // Accounts and proposals (decision D45); the session is an HttpOnly cookie sent automatically.
  me: () => request<{ user: AccountInfo | null }>('/api/auth/me'),
  register: (username: string, password: string) =>
    request<{ user: AccountInfo }>('/api/auth/register', { username, password }),
  login: (username: string, password: string) =>
    request<{ user: AccountInfo }>('/api/auth/login', { username, password }),
  logout: () => request<void>('/api/auth/logout', {}),
  deleteAccount: (password: string) => request<void>('/api/auth/delete-account', { password }),
  propose: (siteId: string, note: string) => request<ProposalInfo>('/api/proposals', { site_id: siteId, note }),
  myProposals: () => request<ProposalInfo[]>('/api/proposals'),
  adminProposals: (status?: ProposalInfo['status']) =>
    request<ProposalInfo[]>(`/api/admin/proposals${status ? `?status=${status}` : ''}`),
  approveProposal: (id: number, body: ApproveBody) =>
    request<ProposalInfo>(`/api/admin/proposals/${id}/approve`, body),
  rejectProposal: (id: number, adminNote: string) =>
    request<ProposalInfo>(`/api/admin/proposals/${id}/reject`, { admin_note: adminNote }),
  removeCommunitySite: (siteId: string) =>
    request<void>(`/api/admin/community-sites/${encodeURIComponent(siteId)}`, undefined, 'DELETE'),
}
