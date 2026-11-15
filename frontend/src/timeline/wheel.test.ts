// ABOUTME: Tests of the time wheel helpers: snapping, clamping to the window, labels
// ABOUTME: Owner: Gian

import { describe, expect, it } from 'vitest'
import { formatOffset, moveOffset, sampleIndex } from './wheel'

describe('moveOffset', () => {
  it('moves by whole sampling steps', () => {
    expect(moveOffset(0, 3, 60, 720)).toBe(3)
    expect(moveOffset(1, -1, 30, 720)).toBe(0.5)
  })
  it('snaps a fractional offset to the step grid', () => {
    expect(moveOffset(2.4, 0, 60, 720)).toBe(2)
  })
  it('stays inside the window', () => {
    expect(moveOffset(1, -5, 60, 720)).toBe(0)
    expect(moveOffset(719, 10, 60, 720)).toBe(720)
  })
})

describe('sampleIndex', () => {
  it('maps an offset to the closest sample', () => {
    expect(sampleIndex(2, 10)).toBe(12)
    expect(sampleIndex(0, 60)).toBe(0)
  })
})

describe('formatOffset', () => {
  it('labels start, minutes, hours and days', () => {
    expect(formatOffset(0)).toBe('start')
    expect(formatOffset(0.75)).toBe('+45 min')
    expect(formatOffset(5)).toBe('+5 h')
    expect(formatOffset(76)).toBe('+3 d 04 h')
  })
})
