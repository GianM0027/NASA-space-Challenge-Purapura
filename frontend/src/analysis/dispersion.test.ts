// ABOUTME: Tests of the touchdown helpers: bearing, compass label, sample class, verdict text
// ABOUTME: Owner: Gian

import { describe, expect, it } from 'vitest'
import type { DispersionSample, VisibilityMetrics } from '../api/contracts'
import { bearingDeg, classify, compass, isSteep, touchdownVerdict } from './dispersion'

const CENTER = { lat_deg: 0, lon_deg: 0 }

function metrics(sun: number, earth: number): VisibilityMetrics {
  return { illumination_fraction: sun, earth_visibility_fraction: earth } as VisibilityMetrics
}

function sample(lat: number, lon: number, offset: number, sun: number, earth: number, slope: number): DispersionSample {
  return { location: { lat_deg: lat, lon_deg: lon, height_m: null }, offset_m: offset, metrics: metrics(sun, earth), slope_max_deg: slope }
}

describe('bearing and compass', () => {
  it('points north, east, south and west', () => {
    expect(compass(bearingDeg(CENTER, { lat_deg: 0.01, lon_deg: 0 }))).toBe('N')
    expect(compass(bearingDeg(CENTER, { lat_deg: 0, lon_deg: 0.01 }))).toBe('E')
    expect(compass(bearingDeg(CENTER, { lat_deg: -0.01, lon_deg: 0 }))).toBe('S')
    expect(compass(bearingDeg(CENTER, { lat_deg: 0, lon_deg: -0.01 }))).toBe('W')
    expect(Math.round(bearingDeg(CENTER, { lat_deg: 0, lon_deg: 0.01 }))).toBe(90)
  })
})

describe('classify', () => {
  const nominal = metrics(0.5, 1)
  it('treats differences under one point as the same', () => {
    expect(classify(sample(0, 0, 50, 0.505, 1, 2), nominal)).toBe('same')
  })
  it('flags less Sun or Earth and more Sun', () => {
    expect(classify(sample(0, 0, 50, 0.4, 1, 2), nominal)).toBe('worse')
    expect(classify(sample(0, 0, 50, 0.5, 0.9, 2), nominal)).toBe('worse')
    expect(classify(sample(0, 0, 50, 0.6, 1, 12), nominal)).toBe('better')
  })
  it('flags a slope over the limit separately', () => {
    expect(isSteep(sample(0, 0, 50, 0.5, 1, 12))).toBe(true)
    expect(isSteep(sample(0, 0, 50, 0.5, 1, 10))).toBe(false)
  })
})

describe('touchdownVerdict', () => {
  it('says the disk matches the target when every point does', () => {
    const text = touchdownVerdict([sample(0.001, 0, 50, 0.5, 1, 1.2), sample(0, 0.003, 100, 0.5, 1, 1.5)], metrics(0.5, 1), CENTER)
    expect(text).toBe(
      'Anywhere within 100 m of the target: Sun 50.0 % (as at the target), Earth 100.0 % (as at the target), landing slope at most 1.5° (limit 10°).',
    )
  })
  it('names the lowest point and counts steep points', () => {
    const text = touchdownVerdict([sample(-0.003, 0, 100, 0.38, 1, 12), sample(0.001, 0, 50, 0.5, 1, 1)], metrics(0.5, 1), CENTER)
    expect(text).toContain('Sun 38.0 % to 50.0 % (target 50.0 %, lowest 100 m S)')
    expect(text).toContain('over the 10° limit at 1 of 2 points (up to 12.0°)')
  })
  it('handles no samples', () => {
    expect(touchdownVerdict([], metrics(0.5, 1), CENTER)).toContain('No touchdown points')
  })
})
