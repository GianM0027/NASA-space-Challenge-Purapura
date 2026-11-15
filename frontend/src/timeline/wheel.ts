// ABOUTME: Pure helpers of the time wheel (spec UI-11): move the shown instant inside the window
// ABOUTME: Owner: Gian. Offsets are hours from the window start, snapped to the sampling step

/** Shown instant after moving `steps` sampling steps, clamped to [0, window length], hours. */
export function moveOffset(offsetH: number, steps: number, stepMinutes: number, windowH: number): number {
  const stepH = stepMinutes / 60
  const snapped = Math.round((offsetH + steps * stepH) / stepH) * stepH
  return Math.min(Math.max(snapped, 0), windowH)
}

/** Index of the evaluation sample closest to an offset, for the timeline cursor. */
export function sampleIndex(offsetH: number, stepMinutes: number): number {
  return Math.round((offsetH * 60) / stepMinutes)
}

/** Offset as a short label: "+3 d 04 h", "+45 min", "start". */
export function formatOffset(offsetH: number): string {
  if (offsetH <= 0) return 'start'
  const totalMinutes = Math.round(offsetH * 60)
  const days = Math.floor(totalMinutes / 1440)
  const hours = Math.floor((totalMinutes % 1440) / 60)
  const minutes = totalMinutes % 60
  if (days === 0 && hours === 0) return `+${minutes} min`
  const parts = days > 0 ? [`${days} d`, `${String(hours).padStart(2, '0')} h`] : [`${hours} h`]
  if (minutes > 0) parts.push(`${String(minutes).padStart(2, '0')} min`)
  return `+${parts.join(' ')}`
}
