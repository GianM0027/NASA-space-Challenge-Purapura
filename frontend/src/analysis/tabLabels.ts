// ABOUTME: Short, distinct labels for the mission analysis tabs ("Apollo 15", "Apollo 15 · 500 m")
// ABOUTME: Owner: Gian. Pure function, unit-tested; the full site name is shown above the results

import type { AnalysisTab } from './MissionAnalysisBox'
import { formatUtc } from '../format'

/**
 * Short tab labels: the site name before " - " ("Apollo 15"), plus what tells two tabs of the same
 * site apart (landing precision, then start date) when needed. The full name is in the view.
 */
export function tabLabels(tabs: Pick<AnalysisTab, 'label' | 'landingPrecisionM' | 'window'>[]): string[] {
  const base = tabs.map((tab) => tab.label.split(' - ')[0].trim() || tab.label)
  return tabs.map((tab, i) => {
    const same = tabs.filter((_, j) => base[j] === base[i])
    if (same.length === 1) return base[i]
    const precisions = new Set(same.map((t) => t.landingPrecisionM))
    if (precisions.size === same.length) return `${base[i]} · ${tab.landingPrecisionM} m`
    return `${base[i]} · ${formatUtc(tab.window.start_utc).slice(5, 10)} · ${tab.landingPrecisionM} m`
  })
}

