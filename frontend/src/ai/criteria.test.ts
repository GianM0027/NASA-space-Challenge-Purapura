// ABOUTME: Tests of the AI box field helpers: formatting, percent editing, setting and clearing fields
// ABOUTME: Owner: Gian

import { describe, expect, it } from 'vitest'
import type { MissionRequirements } from '../api/contracts'
import { fieldValue, formatFieldValue, fromEditable, shownFields, toEditable, withField } from './criteria'

const base = {
  window: null,
  area: null,
  min_illumination_fraction: 0.5,
  max_slope_deg: 8,
  field_sources: { min_illumination_fraction: 'archetype', max_slope_deg: 'user' },
  rationale: {},
} as unknown as MissionRequirements

describe('criteria', () => {
  it('formats each unit', () => {
    expect(formatFieldValue('fraction', 0.256)).toBe('26%')
    expect(formatFieldValue('h', 155.6)).toBe('156 h')
    expect(formatFieldValue('deg', 8)).toBe('8.0°')
    expect(formatFieldValue('m', 2000)).toBe('2.0 km')
    expect(formatFieldValue('m', 100)).toBe('100 m')
  })

  it('edits fractions as percent', () => {
    expect(toEditable('fraction', 0.25)).toBe(25)
    expect(fromEditable('fraction', 25)).toBe(0.25)
    expect(fromEditable('h', 156)).toBe(156)
  })

  it('sets a field by hand and marks it as the user source', () => {
    const edited = withField(base, 'min_illumination_fraction', 0.7)
    expect(fieldValue(edited, 'min_illumination_fraction')).toBe(0.7)
    expect(edited.field_sources.min_illumination_fraction).toBe('user')
  })

  it('clears a field and hides its chip', () => {
    const cleared = withField(base, 'max_slope_deg', null)
    expect(fieldValue(cleared, 'max_slope_deg')).toBeNull()
    expect(shownFields(cleared).map((spec) => spec.field)).toEqual(['min_illumination_fraction'])
  })
})
