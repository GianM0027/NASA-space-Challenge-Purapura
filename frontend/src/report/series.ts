// ABOUTME: Pure helpers on evaluation time series for the report figures (UI-13, D42)
// ABOUTME: Owner: Federico. Unit-tested in ReportDocument.test.tsx

/** Runs of consecutive true samples as [first, last + 1) index pairs. */
export function visibleRuns(visible: boolean[]): [number, number][] {
  const runs: [number, number][] = []
  let start = -1
  visible.forEach((v, k) => {
    if (v && start < 0) start = k
    if (!v && start >= 0) {
      runs.push([start, k])
      start = -1
    }
  })
  if (start >= 0) runs.push([start, visible.length])
  return runs
}
