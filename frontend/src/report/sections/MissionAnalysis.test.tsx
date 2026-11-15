// ABOUTME: Tests of the PDF report section "Mission analysis" (UI-13, D42): structure, static output, numbers
// ABOUTME: Owner: Michael. Renders to static markup with the example robustness report

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import example from '../../../../data/examples/robustness_report.json'
import type { AnalysisTab } from '../../analysis/MissionAnalysisBox'
import type { RobustnessReport, Site } from '../../api/contracts'
import { MissionAnalysis } from './MissionAnalysis'

const report = example as unknown as RobustnessReport

function tab(over: Partial<RobustnessReport> = {}): AnalysisTab {
  return {
    id: 'tab-1',
    label: 'Custom point',
    window: { start_utc: '2026-12-01T00:00:00Z', end_utc: '2026-12-15T00:00:00Z', step_minutes: 60 },
    landingPrecisionM: 100,
    center: { lat_deg: -85.98, lon_deg: -1.67, height_m: null },
    report: { ...report, site_id: 'artemis-malapert-massif', ai_comment: 'Robust to small slips.', ...over },
    commentDone: true,
    error: null,
  }
}

const SITES = [{ id: 'artemis-malapert-massif', name: 'Malapert Massif region' }] as unknown as Site[]

describe('MissionAnalysis section', () => {
  it('has the section root and a numbered heading first', () => {
    const html = renderToStaticMarkup(<MissionAnalysis data={[tab()]} sites={SITES} number={3} />)
    expect(html.startsWith('<section class="rpt-section"><h2>3. Mission analysis</h2>')).toBe(true)
  })

  it('is static: no buttons, inputs, canvas or details', () => {
    const html = renderToStaticMarkup(<MissionAnalysis data={[tab()]} sites={SITES} number={3} />)
    for (const tag of ['<button', '<input', '<canvas', '<details', '<select']) expect(html).not.toContain(tag)
  })

  it('names the site, prints the AI comment, summary and units', () => {
    const html = renderToStaticMarkup(<MissionAnalysis data={[tab()]} sites={SITES} number={3} />)
    expect(html).toContain('Malapert Massif region')
    expect(html).toContain('AI comment: Robust to small slips.')
    expect(html).toContain(' %')
    expect(html).toContain('100 m')
    expect(html).toContain('rpt-table')
  })

  it('prints one block per tab with a report, in order', () => {
    const second = { ...tab(), id: 'tab-2', report: { ...tab().report!, site_id: null }, label: 'Second point' }
    const html = renderToStaticMarkup(<MissionAnalysis data={[tab(), second]} sites={SITES} number={2} />)
    expect(html.indexOf('Malapert Massif region')).toBeLessThan(html.indexOf('Second point'))
  })

  it('adds the Earth outage column only when the Earth is hidden part of the time', () => {
    const always = { ...report.nominal, earth_visibility_fraction: 1, longest_earth_hidden_h: 0 }
    const visible = renderToStaticMarkup(
      <MissionAnalysis
        data={[tab({ nominal: always, date_shifts: [], dispersion: [] })]}
        sites={SITES}
        number={3}
      />,
    )
    expect(visible).not.toContain('longest Earth outage')
    const partial = { ...report.nominal, earth_visibility_fraction: 0.4, longest_earth_hidden_h: 30 }
    const hidden = renderToStaticMarkup(
      <MissionAnalysis
        data={[tab({ nominal: partial, date_shifts: [], dispersion: [] })]}
        sites={SITES}
        number={3}
      />,
    )
    expect(hidden).toContain('longest Earth outage')
    expect(hidden).toContain('Direct-to-Earth link')
  })
})
