// ABOUTME: Requirement fields shown as chips in the AI box: labels, units, formatting, editing
// ABOUTME: Owner: Gian. Pure functions; field names mirror MissionRequirements (lunarnav.ai.assistant)

import type { MissionRequirements, OperationsArea, SiteScore } from '../api/contracts'

export type Unit = 'fraction' | 'h' | 'deg' | 'm'

/** One user-settable requirement field. */
export type FieldSpec = {
  field: string
  label: string
  op: '≥' | '≤' | '='
  unit: Unit
  /** True for fields of `OperationsArea`. */
  area?: boolean
}

/** Every field the AI may fill, in display order; criteria first, then scope and area. */
export const FIELDS: FieldSpec[] = [
  { field: 'min_illumination_fraction', label: 'time in sunlight', op: '≥', unit: 'fraction' },
  { field: 'min_continuous_light_h', label: 'longest light', op: '≥', unit: 'h' },
  { field: 'max_continuous_dark_h', label: 'longest dark', op: '≤', unit: 'h' },
  { field: 'min_sun_elevation_deg', label: 'mean Sun elevation', op: '≥', unit: 'deg' },
  { field: 'min_earth_visibility_fraction', label: 'time with Earth visible', op: '≥', unit: 'fraction' },
  { field: 'min_continuous_earth_visibility_h', label: 'longest contact', op: '≥', unit: 'h' },
  { field: 'max_earth_outage_h', label: 'longest outage', op: '≤', unit: 'h' },
  { field: 'min_sun_and_earth_visible_fraction', label: 'Sun and Earth both visible', op: '≥', unit: 'fraction' },
  { field: 'max_slope_deg', label: 'landing slope', op: '≤', unit: 'deg' },
  { field: 'latitude_min_deg', label: 'latitude', op: '≥', unit: 'deg' },
  { field: 'latitude_max_deg', label: 'latitude', op: '≤', unit: 'deg' },
  { field: 'longitude_min_deg', label: 'longitude from', op: '≥', unit: 'deg' },
  { field: 'longitude_max_deg', label: 'longitude to', op: '≤', unit: 'deg' },
  { field: 'landing_precision_m', label: 'landing precision', op: '=', unit: 'm', area: true },
  { field: 'operating_range_m', label: 'operating range', op: '=', unit: 'm', area: true },
  { field: 'traverse_slope_limit_deg', label: 'traverse slope limit', op: '=', unit: 'deg', area: true },
  { field: 'observer_height_above_ground_m', label: 'panel height', op: '=', unit: 'm', area: true },
]

const BY_FIELD = new Map(FIELDS.map((spec) => [spec.field, spec]))

export function fieldSpec(field: string): FieldSpec | undefined {
  return BY_FIELD.get(field)
}

/** Value as shown to the user: fractions as whole percent, hours whole, degrees one decimal. */
export function formatFieldValue(unit: Unit, value: number): string {
  if (unit === 'fraction') return `${Math.round(value * 100)}%`
  if (unit === 'h') return `${Math.round(value)} h`
  if (unit === 'deg') return `${value.toFixed(1)}°`
  return value >= 1000 ? `${(value / 1000).toFixed(1)} km` : `${Math.round(value)} m`
}

/** Number typed in the edit box for a stored value (fractions are edited as percent). */
export function toEditable(unit: Unit, value: number): number {
  return unit === 'fraction' ? Math.round(value * 1000) / 10 : value
}

/** Stored value for a number typed in the edit box. */
export function fromEditable(unit: Unit, typed: number): number {
  return unit === 'fraction' ? typed / 100 : typed
}

/** Current value of a field, null when unset. */
export function fieldValue(requirements: MissionRequirements, field: string): number | null {
  const spec = BY_FIELD.get(field)
  if (!spec) return null
  const holder = spec.area ? requirements.area : requirements
  if (!holder) return null
  const value = (holder as Record<string, unknown>)[field]
  return typeof value === 'number' ? value : null
}

/** Fields to show as chips: those with a value and a source, in `FIELDS` order. */
export function shownFields(requirements: MissionRequirements): FieldSpec[] {
  return FIELDS.filter(
    (spec) => fieldValue(requirements, spec.field) !== null && spec.field in requirements.field_sources,
  )
}

/**
 * Requirements with one field set by hand (null clears it): its source becomes "user" and the
 * AI keeps it from now on (the caller adds it to the locked fields).
 */
export function withField(
  requirements: MissionRequirements,
  field: string,
  value: number | null,
): MissionRequirements {
  const spec = BY_FIELD.get(field)
  if (!spec) return requirements
  const sources = { ...requirements.field_sources }
  const rationale = { ...requirements.rationale }
  if (value === null) {
    delete sources[field]
    delete rationale[field]
  } else {
    sources[field] = 'user'
    rationale[field] = 'Set by hand in the GUI.'
  }
  if (spec.area) {
    // An area always exists once an area field has a source (the backend sends every field).
    const area = { ...(requirements.area as OperationsArea), [field]: value ?? 0 }
    return { ...requirements, area, field_sources: sources, rationale }
  }
  return { ...requirements, [field]: value, field_sources: sources, rationale }
}

/** Number of set criteria a site meets, out of how many. */
export function constraintsCount(score: SiteScore): [number, number] {
  const values = Object.values(score.constraints_met)
  return [values.filter(Boolean).length, values.length]
}
