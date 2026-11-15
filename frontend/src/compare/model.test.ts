// ABOUTME: Unit tests of the comparison view's pure helpers: active FoMs, validation, request body
// ABOUTME: Owner: Federico (decision D37)

import { describe, expect, it } from 'vitest'
import {
  activeFomIds,
  buildRequest,
  consistencyLabel,
  pairKey,
  pairs,
  parseValue,
  SAATY_OPTIONS,
  judgmentText,
  shortLabel,
  sliderToValue,
  valueToSlider,
  type TradeoffDraft,
  validate,
} from './model'

function draft(overrides: Partial<TradeoffDraft> = {}): TradeoffDraft {
  return {
    scenarios: [
      { label: 'A', siteId: 'im-2', startUtc: '2026-11-14T00:00:00.000Z' },
      { label: 'B', siteId: 'apollo-11', startUtc: '2026-11-20T00:00:00.000Z' },
    ],
    mission: {
      durationHours: 720,
      stepMinutes: 60,
      landingPrecisionM: 100,
      operatingRangeM: 2000,
      traverseLimitDeg: 20,
      observerHeightM: 2,
    },
    excluded: [],
    userFoms: [],
    mode: 'default',
    judgments: {},
    weights: {},
    ...overrides,
  }
}

describe('active FoMs', () => {
  it('lists the six computed FoMs, then user FoMs', () => {
    const ids = activeFomIds(draft({ userFoms: [{ name: 'Cost', unit: 'M$', direction: 'lower', values: ['1', '2'] }] }))
    expect(ids).toHaveLength(7)
    expect(ids[0]).toBe('illumination_fraction')
    expect(ids[6]).toBe('user-1')
  })
  it('drops excluded FoMs and the reachable share without an operating range', () => {
    const base = draft({ excluded: ['longest_dark_h'] })
    expect(activeFomIds(base)).not.toContain('longest_dark_h')
    const noRange = draft({ mission: { ...base.mission, operatingRangeM: 0 } })
    expect(activeFomIds(noRange)).not.toContain('reachable_fraction')
  })
})

describe('validation', () => {
  it('accepts a complete draft', () => {
    expect(validate(draft())).toEqual([])
  })
  it('rejects duplicate names, missing sites and bad user values', () => {
    const errors = validate(
      draft({
        scenarios: [
          { label: 'A', siteId: '', startUtc: '2026-11-14T00:00:00.000Z' },
          { label: 'A', siteId: 'im-2', startUtc: '2026-11-14T00:00:00.000Z' },
        ],
        userFoms: [{ name: '', unit: '', direction: 'higher', values: ['3', '-1'] }],
      }),
    )
    expect(errors).toContain('Pick a site for every scenario.')
    expect(errors).toContain('Scenario names must be different.')
    expect(errors.some((e) => e.includes('needs a name'))).toBe(true)
    expect(errors.some((e) => e.includes('one number >= 0'))).toBe(true)
  })
  it('needs a positive direct weight', () => {
    expect(validate(draft({ mode: 'direct', weights: {} }))).toContain(
      'Give at least one figure of merit a weight above 0.',
    )
  })
})

describe('request body', () => {
  it('builds windows and the shared area per scenario', () => {
    const body = buildRequest(draft())
    expect(body.scenarios[1].window.start_utc).toBe('2026-11-20T00:00:00.000Z')
    expect(body.scenarios[1].window.end_utc).toBe('2026-12-20T00:00:00.000Z')
    expect(body.scenarios[0].area?.operating_range_m).toBe(2000)
    expect(body.settings.labels).toEqual(['A', 'B'])
    expect(body.settings.judgments).toBeUndefined()
    expect(body.settings.weights).toBeUndefined()
  })
  it('sends only non-equal judgments, in matrix order', () => {
    const body = buildRequest(
      draft({ mode: 'judgments', judgments: { [pairKey('illumination_fraction', 'longest_dark_h')]: 3 } }),
    )
    expect(body.settings.judgments).toEqual([
      { a: 'illumination_fraction', b: 'longest_dark_h', value: 3, source: 'user' },
    ])
  })
  it('sends direct weights for every active FoM and user values as numbers', () => {
    const body = buildRequest(
      draft({
        mode: 'direct',
        weights: { illumination_fraction: 2 },
        userFoms: [{ name: 'Cost', unit: 'M$', direction: 'lower', values: ['1,5', '2'] }],
      }),
    )
    expect(body.settings.weights?.illumination_fraction).toBe(2)
    expect(body.settings.weights?.['user-1']).toBe(0)
    expect(body.settings.user_foms?.[0].values).toEqual([1.5, 2])
  })
})

describe('helpers', () => {
  it('pairs the upper triangle', () => {
    expect(pairs(['a', 'b', 'c'])).toEqual([
      ['a', 'b'],
      ['a', 'c'],
      ['b', 'c'],
    ])
  })
  it('parses values and the Saaty scale', () => {
    expect(parseValue('3,5')).toBe(3.5)
    expect(parseValue('-1')).toBeNull()
    expect(parseValue('')).toBeNull()
    expect(SAATY_OPTIONS).toHaveLength(17)
    expect(SAATY_OPTIONS[8].value).toBe(1)
  })
  it('labels the consistency ratio with the 10 % rule', () => {
    expect(consistencyLabel(0.033).ok).toBe(true)
    expect(consistencyLabel(0.2).ok).toBe(false)
    expect(consistencyLabel(null).ok).toBe(true)
  })
})

describe('short labels', () => {
  it('drops region prefixes and site details', () => {
    expect(shortLabel('Artemis candidate region - Malapert Massif')).toBe('Malapert Massif')
    expect(shortLabel('IM-2 Athena - Mons Mouton')).toBe('IM-2 Athena')
    expect(shortLabel('Luna 17 / Lunokhod 1')).toBe('Luna 17 / Lunokhod 1')
  })
})

describe('pairwise slider', () => {
  it('maps positions to the Saaty scale and back', () => {
    expect(sliderToValue(0)).toBe(1)
    expect(sliderToValue(-2)).toBe(3)
    expect(sliderToValue(2)).toBeCloseTo(1 / 3)
    expect(sliderToValue(-8)).toBe(9)
    for (let p = -8; p <= 8; p++) expect(valueToSlider(sliderToValue(p))).toBe(p)
  })
  it('reads the judgment in words', () => {
    expect(judgmentText('Light', 'Dark', 1)).toBe('Equal importance')
    expect(judgmentText('Light', 'Dark', 3)).toBe('Light: 3x, moderately more important')
    expect(judgmentText('Light', 'Dark', 1 / 5)).toBe('Dark: 5x, strongly more important')
  })
})
