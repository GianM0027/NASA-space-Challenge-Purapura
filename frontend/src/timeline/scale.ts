// ABOUTME: Pure helpers of the elevation timeline: visibility bands, vertical range, time ticks
// ABOUTME: Owner: Gian. Index-based x axis: the evaluation samples are evenly spaced (one step)

/** [start, end) sample indices of each run of `true`, in order. */
export function visibleBands(flags: boolean[]): [number, number][] {
  const bands: [number, number][] = []
  let start = -1
  flags.forEach((flag, i) => {
    if (flag && start < 0) start = i
    if (!flag && start >= 0) {
      bands.push([start, i])
      start = -1
    }
  })
  if (start >= 0) bands.push([start, flags.length])
  return bands
}

/**
 * Vertical range of a body's chart, degrees.
 *
 * Covers the body and the horizon with a small margin, always includes 0, and stops 10 degrees
 * below the lowest horizon: deeper below the horizon the exact elevation does not matter.
 */
export function elevationRange(body: number[], horizon: number[]): [number, number] {
  const floor = Math.min(...horizon) - 10
  const low = Math.max(Math.min(...body, ...horizon) - 2, floor)
  const high = Math.max(...body, ...horizon) + 2
  return [Math.min(Math.floor(low), 0), Math.max(Math.ceil(high), 0)]
}

export type Tick = { index: number; label: string }

const TICK_HOURS = [1, 2, 3, 6, 12, 24, 48, 72, 168]

/** Ticks on whole hours or days, at most about six across the window (nine for long windows). */
export function timeTicks(startIso: string, spanHours: number, stepMinutes: number): Tick[] {
  const every = TICK_HOURS.find((hours) => spanHours / hours <= 6) ?? 168
  const start = new Date(startIso).getTime()
  const first = Math.ceil(start / (every * 3_600_000)) * every * 3_600_000
  const ticks: Tick[] = []
  for (let t = first; t <= start + spanHours * 3_600_000; t += every * 3_600_000) {
    const iso = new Date(t).toISOString()
    ticks.push({
      index: Math.round((t - start) / (stepMinutes * 60_000)),
      label: every >= 24 ? iso.slice(5, 10) : iso.slice(11, 16),
    })
  }
  return ticks
}
