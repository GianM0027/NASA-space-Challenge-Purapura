// ABOUTME: Unit tests of the report section selection: availability, print order and numbering
// ABOUTME: Owner: Federico (decision D42)

import { describe, expect, it } from 'vitest'
import type { AnalysisTab } from '../analysis/MissionAnalysisBox'
import type { Evaluation, RobustnessReport, SiteRanking, TradeoffResult } from '../api/contracts'
import { defaultChecked, isAvailable, selectedSections } from './selection'
import type { ReportInputs } from './types'

const window = { start_utc: '2026-11-14T00:00:00Z', end_utc: '2026-12-14T00:00:00Z', step_minutes: 60 }

function inputs(overrides: Partial<ReportInputs> = {}): ReportInputs {
  return { sites: [], window, evaluation: null, analyses: [], ranking: null, tradeoff: null, ...overrides }
}

function tab(report: RobustnessReport | null): AnalysisTab {
  return {
    id: 't',
    label: 'IM-2',
    window,
    landingPrecisionM: 100,
    center: { lat_deg: -84, lon_deg: 29, height_m: null },
    report,
    commentDone: true,
    error: null,
  }
}

describe('report sections', () => {
  it('offers only cover and sources in an empty session', () => {
    expect([...defaultChecked(inputs())]).toEqual(['cover', 'sources'])
  })

  it('needs a finished analysis tab and a non-empty ranking', () => {
    expect(isAvailable('analysis', inputs({ analyses: [tab(null)] }))).toBe(false)
    expect(isAvailable('analysis', inputs({ analyses: [tab({} as RobustnessReport)] }))).toBe(true)
    expect(isAvailable('ranking', inputs({ ranking: { results: [] } as unknown as SiteRanking }))).toBe(false)
  })

  it('prints checked and available sections in fixed order, numbered from 1', () => {
    const full = inputs({ evaluation: {} as Evaluation, tradeoff: {} as TradeoffResult })
    const picked = selectedSections(full, new Set(['tradeoff', 'site', 'ranking']))
    expect(picked.map((s) => [s.id, s.number])).toEqual([
      ['site', 1],
      ['tradeoff', 2],
    ])
  })
})
