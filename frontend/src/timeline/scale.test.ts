// ABOUTME: Tests of the timeline helpers: visibility bands, vertical range and time ticks
// ABOUTME: Known answers; bands must match the engine's per-sample visibility exactly

import { describe, expect, it } from 'vitest'
import { elevationRange, timeTicks, visibleBands } from './scale'

describe('visibleBands', () => {
  it('returns [start, end) index pairs of visible runs', () =>
    expect(visibleBands([false, true, true, false, true])).toEqual([
      [1, 3],
      [4, 5],
    ]))
  it('handles all visible', () => expect(visibleBands([true, true])).toEqual([[0, 2]]))
  it('handles never visible', () => expect(visibleBands([false, false])).toEqual([]))
})

describe('elevationRange', () => {
  it('spans body and horizon with margins', () =>
    expect(elevationRange([2, 10], [0, 5])).toEqual([-2, 12]))
  it('does not go more than 10 degrees below the lowest horizon', () =>
    expect(elevationRange([-80, 20], [0, 4])).toEqual([-10, 22]))
  it('always shows the 0 degree line', () =>
    expect(elevationRange([30, 40], [20, 25])).toEqual([0, 42]))
})

describe('timeTicks', () => {
  const start = '2027-01-01T00:00:00Z'
  it('places ticks at whole days for multi-day windows', () => {
    const ticks = timeTicks(start, 4 * 24, 60)
    expect(ticks.map((tick) => tick.label)).toEqual([
      '01-01',
      '01-02',
      '01-03',
      '01-04',
      '01-05',
    ])
    expect(ticks[1].index).toBe(24)
  })
  it('uses hours for windows of a day', () => {
    const ticks = timeTicks(start, 24, 60)
    expect(ticks[0].label).toBe('00:00')
    expect(ticks[1].index).toBe(6)
  })
  it('keeps at most about eight ticks', () =>
    expect(timeTicks(start, 60 * 24, 60).length).toBeLessThanOrEqual(9))
})
