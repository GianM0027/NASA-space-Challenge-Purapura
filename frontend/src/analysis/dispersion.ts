// ABOUTME: Pure helpers of the touchdown view (spec UI-5): direction, class and verdict per sample
// ABOUTME: Owner: Gian. Reads only RobustnessReport numbers; thresholds are display choices, stated

import type { DispersionSample, GeoPoint, VisibilityMetrics } from '../api/contracts'
import { formatPercent } from '../format'

/** Differences smaller than this, as a fraction (1 percentage point), count as "as at the target". */
export const SAME_FRACTION = 0.01

/** Landing slope limit, degrees: NASA HLS "surface slope for landing (100 m) < 10 deg" (HLS Overview 2025, p. 21). */
export const SLOPE_LIMIT_DEG = 10

export type SampleClass = 'same' | 'better' | 'worse'

/** A position on the Moon: only latitude and longitude matter here. */
type LatLon = Pick<GeoPoint, 'lat_deg' | 'lon_deg'>

const COMPASS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']

/** Initial great-circle bearing from `from` to `to`, degrees clockwise from north in [0, 360). */
export function bearingDeg(from: LatLon, to: LatLon): number {
  const rad = Math.PI / 180
  const lat1 = from.lat_deg * rad
  const lat2 = to.lat_deg * rad
  const dLon = (to.lon_deg - from.lon_deg) * rad
  const y = Math.sin(dLon) * Math.cos(lat2)
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon)
  return ((Math.atan2(y, x) / rad) % 360 + 360) % 360
}

/** Eight-point compass label of a bearing ("N", "NE", ...). */
export function compass(bearing: number): string {
  return COMPASS[Math.round(bearing / 45) % 8]
}

/** Whether a touchdown point's landing slope is over the limit. */
export function isSteep(sample: DispersionSample): boolean {
  return sample.slope_max_deg > SLOPE_LIMIT_DEG
}

/** How a sample's Sun and Earth visibility compare with the target point. */
export function classify(sample: DispersionSample, nominal: VisibilityMetrics): SampleClass {
  const sun = sample.metrics.illumination_fraction - nominal.illumination_fraction
  const earth = sample.metrics.earth_visibility_fraction - nominal.earth_visibility_fraction
  if (sun <= -SAME_FRACTION || earth <= -SAME_FRACTION) return 'worse'
  if (sun >= SAME_FRACTION || earth >= SAME_FRACTION) return 'better'
  return 'same'
}

/** "Sun 50.9 % (as at the target)" or "Sun 38.0 % to 52.1 % (lowest 100 m S)". */
function rangeText(
  label: string,
  pick: (metrics: VisibilityMetrics) => number,
  samples: DispersionSample[],
  nominal: VisibilityMetrics,
  center: LatLon,
): string {
  const values = samples.map((sample) => pick(sample.metrics))
  const low = Math.min(...values)
  const high = Math.max(...values)
  const target = pick(nominal)
  if (high - target < SAME_FRACTION && target - low < SAME_FRACTION) {
    return `${label} ${formatPercent(target)} (as at the target)`
  }
  const lowest = samples[values.indexOf(low)]
  const where = `${Math.round(lowest.offset_m)} m ${compass(bearingDeg(center, lowest.location))}`
  return `${label} ${formatPercent(low)} to ${formatPercent(high)} (target ${formatPercent(target)}, lowest ${where})`
}

/** One sentence on the whole disk, with numbers from the report only. */
export function touchdownVerdict(
  samples: DispersionSample[],
  nominal: VisibilityMetrics,
  center: LatLon,
): string {
  if (samples.length === 0) return 'No touchdown points to compare (landing precision 0 m).'
  const radius = Math.round(Math.max(...samples.map((sample) => sample.offset_m)))
  const steepest = samples.reduce((a, b) => (b.slope_max_deg > a.slope_max_deg ? b : a))
  const steep = samples.filter((sample) => sample.slope_max_deg > SLOPE_LIMIT_DEG).length
  const slope =
    steep > 0
      ? `landing slope over the ${SLOPE_LIMIT_DEG}° limit at ${steep} of ${samples.length} points (up to ${steepest.slope_max_deg.toFixed(1)}°)`
      : `landing slope at most ${steepest.slope_max_deg.toFixed(1)}° (limit ${SLOPE_LIMIT_DEG}°)`
  const sun = rangeText('Sun', (m) => m.illumination_fraction, samples, nominal, center)
  const earth = rangeText('Earth', (m) => m.earth_visibility_fraction, samples, nominal, center)
  return `Anywhere within ${radius} m of the target: ${sun}, ${earth}, ${slope}.`
}
