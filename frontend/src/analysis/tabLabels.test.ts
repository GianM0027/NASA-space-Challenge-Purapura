// ABOUTME: Tests of the mission analysis tab labels: short names, told apart only when needed
// ABOUTME: Owner: Gian. Known answers for one, two and three tabs

import { describe, expect, it } from 'vitest'
import { tabLabels } from './tabLabels'

const tab = (label: string, landingPrecisionM = 100, start = '2026-11-27T00:00:00Z') => ({
  label,
  landingPrecisionM,
  window: { start_utc: start, end_utc: '2026-12-27T00:00:00Z', step_minutes: 60 },
})

describe('tabLabels', () => {
  it('keeps the name before the dash', () => {
    expect(tabLabels([tab('Apollo 15 - Hadley-Apennine'), tab('Apollo 12 - Ocean of Storms')])).toEqual([
      'Apollo 15',
      'Apollo 12',
    ])
  })

  it('adds the landing precision when the same site is analyzed twice', () => {
    expect(tabLabels([tab('Apollo 15 - Hadley', 100), tab('Apollo 15 - Hadley', 500)])).toEqual([
      'Apollo 15 · 100 m',
      'Apollo 15 · 500 m',
    ])
  })

  it('adds the start date when precision alone does not tell them apart', () => {
    const labels = tabLabels([tab('X', 100, '2026-11-27T00:00:00Z'), tab('X', 100, '2026-12-05T00:00:00Z')])
    expect(labels[0]).not.toEqual(labels[1])
  })

  it('keeps names without a dash, such as coordinates', () => {
    expect(tabLabels([tab('12.97° N, 11.51° W')])).toEqual(['12.97° N, 11.51° W'])
  })
})
