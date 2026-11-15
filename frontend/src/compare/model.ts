// ABOUTME: Pure state helpers of the comparison and trade-off view (UI-3, TO-1 to TO-4): request, Saaty scale
// ABOUTME: Owner: Federico (decision D37). No React here, so every rule is unit-tested

import type {
  EvaluateRequest,
  FomDirection,
  PairwiseJudgment,
  TradeoffRequest,
  TradeoffSettingsInput,
} from '../api/contracts'

/** Computed FoM ids, in the order of the trade-off module (lunarnav.tradeoff.foms). */
export const COMPUTED_FOMS: { id: string; name: string; unit: string; direction: FomDirection }[] = [
  { id: 'illumination_fraction', name: 'Sunlit time', unit: '', direction: 'higher' },
  { id: 'longest_dark_h', name: 'Longest darkness', unit: 'h', direction: 'lower' },
  { id: 'earth_visibility_fraction', name: 'Earth in view', unit: '', direction: 'higher' },
  { id: 'longest_earth_hidden_h', name: 'Longest Earth outage', unit: 'h', direction: 'lower' },
  { id: 'landing_slope_max_deg', name: 'Landing slope (P99, 100 m)', unit: 'deg', direction: 'lower' },
  { id: 'reachable_fraction', name: 'Reachable area', unit: '', direction: 'higher' },
]

export const MAX_SCENARIOS = 4
export const MIN_SCENARIOS = 2
export const MAX_USER_FOMS = 3
export const CR_LIMIT = 0.1

/** Saaty scale as shown in a select: "a is v times as important as b", v from 9 down to 1/9. */
export const SAATY_OPTIONS: { value: number; label: string }[] = [
  ...[9, 8, 7, 6, 5, 4, 3, 2].map((v) => ({ value: v, label: `${v}` })),
  { value: 1, label: '1 (equal)' },
  ...[2, 3, 4, 5, 6, 7, 8, 9].map((v) => ({ value: 1 / v, label: `1/${v}` })),
]

export type Scenario = { label: string; siteId: string; startUtc: string }

export type Mission = {
  durationHours: number
  stepMinutes: number
  landingPrecisionM: number
  operatingRangeM: number
  traverseLimitDeg: number
  observerHeightM: number
}

export type UserFomDraft = { name: string; unit: string; direction: FomDirection; values: string[] }

export type WeightMode = 'default' | 'judgments' | 'direct'

export type TradeoffDraft = {
  scenarios: Scenario[]
  mission: Mission
  excluded: string[]
  userFoms: UserFomDraft[]
  mode: WeightMode
  /** Pair key "a|b" (a before b in FoM order) -> Saaty value of a over b. */
  judgments: Record<string, number>
  /** FoM id -> direct weight (any scale; the backend normalizes). */
  weights: Record<string, number>
}

/** FoM ids taking part in the trade-off, in order: computed ones not excluded, then user ones. */
export function activeFomIds(draft: TradeoffDraft): string[] {
  // Without an operating range the reachable share is not defined (TerrainStats, D32).
  const noRange = draft.mission.operatingRangeM <= 0
  const computed = COMPUTED_FOMS.map((f) => f.id).filter(
    (id) => !draft.excluded.includes(id) && !(noRange && id === 'reachable_fraction'),
  )
  return [...computed, ...draft.userFoms.map((_, k) => `user-${k + 1}`)]
}

/** Every unordered pair of ids, in matrix order (upper triangle). */
export function pairs(ids: string[]): [string, string][] {
  const out: [string, string][] = []
  ids.forEach((a, i) => ids.slice(i + 1).forEach((b) => out.push([a, b])))
  return out
}

export const pairKey = (a: string, b: string) => `${a}|${b}`

/** Parse a user FoM value; null when it is not a finite number >= 0. */
export function parseValue(text: string): number | null {
  if (text.trim() === '') return null
  const value = Number(text.replace(',', '.'))
  return Number.isFinite(value) && value >= 0 ? value : null
}

/** Problems that block a run, as short messages; empty when the draft can be sent. */
export function validate(draft: TradeoffDraft): string[] {
  const errors: string[] = []
  const n = draft.scenarios.length
  if (n < MIN_SCENARIOS || n > MAX_SCENARIOS) errors.push(`Compare ${MIN_SCENARIOS} to ${MAX_SCENARIOS} scenarios.`)
  if (draft.scenarios.some((s) => !s.siteId)) errors.push('Pick a site for every scenario.')
  const labels = draft.scenarios.map((s) => s.label.trim())
  if (labels.some((l) => l === '')) errors.push('Give every scenario a name.')
  if (new Set(labels).size !== labels.length) errors.push('Scenario names must be different.')
  draft.userFoms.forEach((fom, k) => {
    if (!fom.name.trim()) errors.push(`User FoM ${k + 1} needs a name.`)
    if (fom.values.length !== n || fom.values.some((v) => parseValue(v) === null)) {
      errors.push(`User FoM ${k + 1}: enter one number >= 0 per scenario.`)
    }
  })
  const ids = activeFomIds(draft)
  if (ids.length === 0) errors.push('Keep at least one figure of merit.')
  if (ids.length > 9) errors.push('At most 9 figures of merit (Saaty).')
  if (draft.mode === 'direct' && !ids.some((id) => (draft.weights[id] ?? 0) > 0)) {
    errors.push('Give at least one figure of merit a weight above 0.')
  }
  return errors
}

/** Scenario requests, as /api/evaluate takes them, with the shared mission settings. */
export function scenarioRequests(draft: TradeoffDraft): EvaluateRequest[] {
  const m = draft.mission
  return draft.scenarios.map((s) => {
    const start = new Date(s.startUtc)
    const end = new Date(start.getTime() + m.durationHours * 3_600_000)
    return {
      site_id: s.siteId,
      window: { start_utc: start.toISOString(), end_utc: end.toISOString(), step_minutes: m.stepMinutes },
      area: {
        landing_precision_m: m.landingPrecisionM,
        operating_range_m: m.operatingRangeM,
        traverse_slope_limit_deg: m.traverseLimitDeg,
        observer_height_above_ground_m: m.observerHeightM,
      },
    }
  })
}

/** The /api/tradeoff body for the draft (call validate first). */
export function buildRequest(draft: TradeoffDraft): TradeoffRequest {
  const ids = activeFomIds(draft)
  const settings: TradeoffSettingsInput = {
    labels: draft.scenarios.map((s) => s.label.trim()),
    excluded_foms: [...draft.excluded],
    user_foms: draft.userFoms.map((fom) => ({
      name: fom.name.trim(),
      unit: fom.unit.trim(),
      direction: fom.direction,
      values: fom.values.map((v) => parseValue(v) ?? 0),
    })),
  }
  if (draft.mode === 'direct') {
    settings.weights = Object.fromEntries(ids.map((id) => [id, draft.weights[id] ?? 0]))
  } else if (draft.mode === 'judgments') {
    settings.judgments = pairs(ids)
      .map(([a, b]): PairwiseJudgment => ({ a, b, value: draft.judgments[pairKey(a, b)] ?? 1, source: 'user' }))
      .filter((j) => j.value !== 1)
  }
  return { scenarios: scenarioRequests(draft), settings }
}

/** Saaty consistency label for a ratio, with the 10 % rule. */
export function consistencyLabel(cr: number | null): { text: string; ok: boolean } {
  if (cr === null) return { text: 'not applicable (direct weights)', ok: true }
  const pct = `${(cr * 100).toFixed(1)} %`
  return cr <= CR_LIMIT + 1e-12 ? { text: `${pct}: consistent`, ok: true } : { text: `${pct}: above 10 %, revise the judgments`, ok: false }
}

/** "1st", "2nd", ... for a 0-based position. */
export function ordinal(position: number): string {
  const n = position + 1
  return n === 1 ? '1st' : n === 2 ? '2nd' : n === 3 ? '3rd' : `${n}th`
}

/** Short scenario label from a catalog name: "Artemis candidate region - Malapert Massif" -> "Malapert Massif". */
export function shortLabel(siteName: string): string {
  const name = siteName.replace(/^Artemis candidate region - /, '')
  return name.split(' - ')[0].trim() || siteName
}

/**
 * Pairwise slider: position -8..8. Left (negative) favours the first FoM: -2 means it is 3 times
 * as important (Saaty 3); 0 is equal; +2 means the second is 3 times as important (1/3).
 */
export const SLIDER_MAX = 8

export function sliderToValue(position: number): number {
  return position <= 0 ? 1 - position : 1 / (1 + position)
}

export function valueToSlider(value: number): number {
  // Math.round(1 - value) instead of -Math.round(value - 1): the latter gives -0 for equal.
  return value >= 1 ? Math.round(1 - value) : Math.round(1 / value - 1)
}

/** Saaty's verbal scale (Governale et al. 2021, Table 1), for the slider readout. */
export function saatyWord(times: number): string {
  if (times >= 9) return 'extremely'
  if (times >= 7) return 'very strongly'
  if (times >= 5) return 'strongly'
  if (times >= 3) return 'moderately'
  return 'slightly'
}

/** Readout of a judgment of a over b, e.g. "Sunlit time: 3x, moderately more important". */
export function judgmentText(a: string, b: string, value: number): string {
  if (value === 1) return 'Equal importance'
  const [winner, times] = value > 1 ? [a, value] : [b, Math.round(1 / value)]
  return `${winner}: ${times}x, ${saatyWord(times)} more important`
}
