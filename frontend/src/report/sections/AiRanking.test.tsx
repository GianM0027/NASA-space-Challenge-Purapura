// ABOUTME: Smoke test of the "AI assistant ranking" report section: title, request, sites, scores
// ABOUTME: Owner: Gian. Renders to static markup, as window.print() sees it

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { Site, SiteRanking, SiteScore } from '../../api/contracts'
import { AiRanking } from './AiRanking'

function score(siteId: string, rank: number, passes: boolean): SiteScore {
  return {
    site_id: siteId,
    rank,
    score: passes ? 0.83 : 0,
    constraints_met: { min_illumination_fraction: passes, max_slope_deg: true },
    criterion_values: { min_illumination_fraction: passes ? 0.7 : 0.3, max_slope_deg: 4 },
    all_constraints_met: passes,
    landing_slope_max_deg: 4,
    rationale: passes ? 'Lit 70 % of the time.' : null,
  } as unknown as SiteScore
}

const ranking = {
  requirements: {
    min_illumination_fraction: 0.5,
    max_slope_deg: 10,
    archetype_id: 'polar-rover',
    region_id: 'south-pole',
    field_sources: { min_illumination_fraction: 'user', max_slope_deg: 'archetype' },
    rationale: {},
    source_request: 'A rover near the south pole',
    window: { start_utc: '2026-12-01T00:00:00Z', end_utc: '2026-12-15T00:00:00Z', step_minutes: 60 },
  },
  results: [score('pole', 1, true), score('rim', 2, false)],
  weights: { min_illumination_fraction: 0.5, max_slope_deg: 0.5 },
  unavailable: { broken: 'DEM missing' },
} as unknown as SiteRanking

const sites = [{ id: 'pole', name: 'Pole Site' }] as Site[]

describe('AiRanking section', () => {
  it('prints the numbered title, the request, the named sites and their scores', () => {
    const html = renderToStaticMarkup(<AiRanking data={ranking} sites={sites} number={4} />)
    expect(html).toContain('<section class="rpt-section"><h2>4. AI assistant ranking</h2>')
    expect(html).toContain('A rover near the south pole')
    expect(html).toContain('south-pole')
    expect(html).toContain('Pole Site')
    expect(html).toContain('0.83')
    expect(html).toContain('1 landing sites could not be evaluated')
  })

  it('prints no interactive element', () => {
    const html = renderToStaticMarkup(<AiRanking data={ranking} sites={sites} number={1} />)
    expect(html).not.toMatch(/<(button|input|select|canvas)/)
  })
})
