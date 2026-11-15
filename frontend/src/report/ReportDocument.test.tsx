// ABOUTME: Smoke tests of the printable report: sections appear only when ticked and available, with their numbers
// ABOUTME: Owner: Federico (decision D42). Server-side rendering, no DOM needed

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { Evaluation, TradeoffResult } from '../api/contracts'
import { ReportDocument } from './ReportBuilder'
import { visibleRuns } from './series'
import type { ReportInputs, SectionId } from './types'

const window = { start_utc: '2026-11-14T00:00:00Z', end_utc: '2026-12-14T00:00:00Z', step_minutes: 60 }

const tradeoff: TradeoffResult = {
  labels: ['Apollo 11', 'IM-2 Athena'],
  foms: [{ id: 'illumination_fraction', name: 'Sunlit time', unit: '', direction: 'higher', user_supplied: false, source: '' }],
  weights: { illumination_fraction: 1 },
  weight_method: 'default',
  judgments: [],
  consistency_ratio: 0,
  table: [
    { illumination_fraction: { value: 0.49, normalized: 0.486 } },
    { illumination_fraction: { value: 0.519, normalized: 0.514 } },
  ],
  scores: [0.486, 0.514],
  ranking: [1, 0],
  method: 'AHP, single level',
  sensitivity: [{ fom_id: 'illumination_fraction', min_change_percent: null, sensitivity: null }],
  ai_comment: null,
}

function render(checked: SectionId[], overrides: Partial<ReportInputs> = {}): string {
  const inputs: ReportInputs = { sites: [], window, evaluation: null, analyses: [], ranking: null, tradeoff: null, ...overrides }
  return renderToStaticMarkup(
    <ReportDocument inputs={inputs} checked={new Set(checked)} title="Test report" generatedUtc="2026-11-15T10:00:00Z" />,
  )
}

describe('report document', () => {
  it('shows the trade-off ranking and details when ticked', () => {
    const html = render(['cover', 'tradeoff'], { tradeoff })
    expect(html).toContain('Test report')
    expect(html).toContain('1. Trade-off')
    expect(html).toContain('Details per criterion')
    expect(html.indexOf('IM-2 Athena')).toBeLessThan(html.indexOf('0.486'))
    expect(html).toContain('51.9 %')
  })

  it('drops a section without data or without a tick', () => {
    expect(render(['tradeoff'])).not.toContain('Trade-off')
    expect(render(['cover'], { tradeoff })).not.toContain('Details per criterion')
    expect(render(['site'], { evaluation: null })).toContain('Tick at least one section')
  })

  it('does not print sections still to be written (mission analysis, AI ranking)', () => {
    const html = render(['analysis', 'sources'], { evaluation: null })
    expect(html).toContain('1. Sources and methods')
    expect(html).not.toContain('Mission analysis')
  })

  it('renders the site evaluation without errors', () => {
    const evaluation = {
      site_id: null,
      location: { lat_deg: -84.6, lon_deg: 29.2, height_m: null },
      window,
      area: { landing_precision_m: 100, operating_range_m: 0, traverse_slope_limit_deg: 20, observer_height_above_ground_m: 2 },
      times_utc: ['2026-11-14T00:00:00Z', '2026-11-14T01:00:00Z', '2026-11-14T02:00:00Z'],
      sun_visible: [true, false, true],
      earth_visible: [true, true, true],
      terrain: {
        elevation_m: 1200,
        landing_radius_m: 100,
        landing_slope_mean_deg: 2,
        landing_slope_max_deg: 4.1,
        radius_m: 100,
        slope_mean_deg: 2,
        slope_max_deg: 4.1,
        traverse_slope_limit_deg: 20,
        reachable_fraction: null,
        dem_source: 'LDEM_85S_20M',
        dem_resolution_m: 20,
      },
      metrics: {
        illumination_fraction: 0.667,
        earth_visibility_fraction: 1,
        longest_light_h: 1,
        longest_light_truncated: true,
        longest_dark_h: 1,
        longest_dark_truncated: false,
        longest_earth_visible_h: 3,
        longest_earth_visible_truncated: true,
        longest_earth_hidden_h: 0,
        longest_earth_hidden_truncated: false,
        sun_elevation_mean_visible_deg: 1.5,
        earth_elevation_mean_visible_deg: null,
        sun_and_earth_visible_fraction: 0.667,
      },
    } as unknown as Evaluation
    const html = render(['site'], { evaluation })
    expect(html).toContain('1. Site evaluation: custom point')
    expect(html).toContain('66.7 %')
    expect(html).toContain('n/a (no rover range)')
  })
})

describe('visibility runs', () => {
  it('finds the visible stretches, also at the window edges', () => {
    expect(visibleRuns([true, true, false, true])).toEqual([
      [0, 2],
      [3, 4],
    ])
    expect(visibleRuns([false, false])).toEqual([])
  })
})
