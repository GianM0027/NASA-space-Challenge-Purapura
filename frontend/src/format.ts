// ABOUTME: Display formatters shared by the panels: durations, coordinates, UTC date inputs
// ABOUTME: Owner: Gian. All times are UTC; nothing here uses the browser's local time zone

/** "30 min", "5 h", "3 d 4 h": a duration in hours, rounded to the minute or hour. */
export function formatDuration(hours: number): string {
  if (hours < 1) return `${Math.round(hours * 60)} min`
  const whole = Math.round(hours)
  const days = Math.floor(whole / 24)
  const rest = whole % 24
  if (days === 0) return `${rest} h`
  return rest === 0 ? `${days} d` : `${days} d ${rest} h`
}

/** "89.50° S, 23.47° E" from signed degrees. */
export function formatCoordinates(point: { lat_deg: number; lon_deg: number }): string {
  const lat = `${Math.abs(point.lat_deg).toFixed(2)}° ${point.lat_deg < 0 ? 'S' : 'N'}`
  const lon = `${Math.abs(point.lon_deg).toFixed(2)}° ${point.lon_deg < 0 ? 'W' : 'E'}`
  return `${lat}, ${lon}`
}

/** ISO instant to the value of a datetime-local input, read as UTC. */
export function toInputValue(isoUtc: string): string {
  return new Date(isoUtc).toISOString().slice(0, 16)
}

/** Value of a datetime-local input, read as UTC, to an ISO instant. */
export function fromInputValue(value: string): string {
  return new Date(`${value}:00Z`).toISOString()
}

/** "2027-01-05 08:30 UTC". */
export function formatUtc(isoUtc: string): string {
  return `${new Date(isoUtc).toISOString().slice(0, 16).replace('T', ' ')} UTC`
}

/** Hours from one ISO instant to another (negative if `to` is earlier). */
export function hoursBetween(fromIso: string, toIso: string): number {
  return (new Date(toIso).getTime() - new Date(fromIso).getTime()) / 3_600_000
}

/** "62.5 %" from a fraction in [0, 1]. */
export function formatPercent(fraction: number): string {
  return `${(fraction * 100).toFixed(1)} %`
}

/** A duration that may be a lower bound: "≥ 3 d 4 h" when the run touches the window edge. */
export function formatAtLeast(hours: number, truncated: boolean): string {
  const text = formatDuration(hours)
  return truncated && hours > 0 ? `≥ ${text}` : text
}
