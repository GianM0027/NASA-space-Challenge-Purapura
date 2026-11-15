// ABOUTME: PDF report section "Mission analysis" (UI-13, D42): date slips, landing dispersion, Earth link, AI comment
// ABOUTME: Owner: Michael. Static HTML/SVG only; wording reuses the analysis window helpers so both say the same

import type { DispersionSample, GeoPoint, Site, VisibilityMetrics } from '../../api/contracts'
import type { AnalysisTab } from '../../analysis/MissionAnalysisBox'
import { bearingDeg, classify, compass, isSteep, SLOPE_LIMIT_DEG, touchdownVerdict } from '../../analysis/dispersion'
import { formatAtLeast, formatCoordinates, formatPercent, formatShiftDays, formatUtc } from '../../format'
import type { MissionAnalysisSectionProps } from '../types'

/** Signed difference of two fractions in percentage points: "-12 pp", "±0". */
function deltaPoints(value: number, nominal: number): string {
  const points = Math.round((value - nominal) * 100)
  return points === 0 ? '±0' : `${points > 0 ? '+' : ''}${points} pp`
}

/** Display name of the analyzed point: the catalog site when the report names one, else the tab label. */
function siteName(tab: AnalysisTab, sites: Site[]): string {
  const id = tab.report?.site_id
  return sites.find((site) => site.id === id)?.name ?? tab.label
}

/** Whether the Earth is hidden part of the time in any case of the report (then the link section is printed). */
function earthMatters(cases: VisibilityMetrics[]): boolean {
  return cases.some((metrics) => metrics.earth_visibility_fraction < 1)
}

/** One row of the date-slip table. */
function ShiftRow(props: { label: string; metrics: VisibilityMetrics; nominal: VisibilityMetrics; earth: boolean }) {
  const { label, metrics, nominal, earth } = props
  return (
    <tr>
      <td>{label}</td>
      <td>
        {formatPercent(metrics.illumination_fraction)}
        {label !== 'nominal' && ` (${deltaPoints(metrics.illumination_fraction, nominal.illumination_fraction)})`}
      </td>
      <td>{formatAtLeast(metrics.longest_dark_h, metrics.longest_dark_truncated)}</td>
      <td>{formatPercent(metrics.earth_visibility_fraction)}</td>
      {earth && <td>{formatAtLeast(metrics.longest_earth_hidden_h, metrics.longest_earth_hidden_truncated)}</td>}
    </tr>
  )
}

const SIZE = 160
const RING = 60
const KIND_LABEL: Record<string, string> = {
  same: 'as at the target',
  better: 'more Sun or Earth',
  worse: 'less Sun or Earth',
}

/** Static target diagram: the analyzed point in the middle, each touchdown sample where it lies. */
function TouchdownFigure(props: { samples: DispersionSample[]; nominal: VisibilityMetrics; center: GeoPoint }) {
  const { samples, nominal, center } = props
  const radius = Math.max(...samples.map((sample) => sample.offset_m))
  const mid = SIZE / 2
  const rings = [...new Set(samples.map((sample) => Math.round(sample.offset_m)))].sort((a, b) => a - b)
  const fill: Record<string, string> = { same: '#9aa5b1', better: '#2e9d5b', worse: '#d0453f' }
  return (
    <figure className="rpt-figure">
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} width="45%" role="img" aria-label="Touchdown points around the target">
        {rings.map((ring) => (
          <g key={ring}>
            <circle cx={mid} cy={mid} r={(ring / radius) * RING} fill="none" stroke="#888" strokeDasharray="2 2" />
            <text x={mid + 3} y={mid - (ring / radius) * RING - 2} fontSize="8" fill="#555">
              {ring} m
            </text>
          </g>
        ))}
        {(['N', 'E', 'S', 'W'] as const).map((label, k) => (
          <text
            key={label}
            x={mid + Math.sin((k * Math.PI) / 2) * (RING + 11)}
            y={mid - Math.cos((k * Math.PI) / 2) * (RING + 11) + 3}
            fontSize="9"
            textAnchor="middle"
            fill="#333"
          >
            {label}
          </text>
        ))}
        <circle cx={mid} cy={mid} r={4} fill="#1f5fbf" />
        {samples.map((sample, i) => {
          const bearing = (bearingDeg(center, sample.location) * Math.PI) / 180
          const r = (sample.offset_m / radius) * RING
          const kind = classify(sample, nominal)
          return (
            <circle
              key={i}
              cx={mid + Math.sin(bearing) * r}
              cy={mid - Math.cos(bearing) * r}
              r={5}
              fill={fill[kind]}
              stroke={isSteep(sample) ? '#d0453f' : 'none'}
              strokeWidth={isSteep(sample) ? 2 : 0}
            />
          )
        })}
      </svg>
      <figcaption>
        Blue: target point. Dots: touchdown points ({[...new Set(samples.map((s) => KIND_LABEL[classify(s, nominal)]))].join(', ')}
        ); red ring: landing slope over {SLOPE_LIMIT_DEG}°. North up.
      </figcaption>
    </figure>
  )
}

/** Everything printed for one analysis tab. */
function TabReport({ tab, sites }: { tab: AnalysisTab; sites: Site[] }) {
  const report = tab.report
  if (!report) return null
  const samples = report.dispersion
  const cases = [report.nominal, ...report.date_shifts.map((s) => s.metrics), ...samples.map((s) => s.metrics)]
  const earth = earthMatters(cases)
  return (
    <div>
      <h3>{siteName(tab, sites)}</h3>
      <table className="rpt-kv">
        <tbody>
          <tr>
            <th>Target point</th>
            <td>{formatCoordinates(tab.center)}</td>
          </tr>
          <tr>
            <th>Window</th>
            <td>
              {formatUtc(tab.window.start_utc)} to {formatUtc(tab.window.end_utc)}
            </td>
          </tr>
          <tr>
            <th>Landing precision</th>
            <td>{Math.round(tab.landingPrecisionM)} m</td>
          </tr>
        </tbody>
      </table>

      {report.ai_comment && <p className="rpt-note">AI comment: {report.ai_comment}</p>}
      {report.summary && <p className="rpt-note">Summary: {report.summary}</p>}

      <h4>If the launch slips</h4>
      <table className="rpt-table">
        <thead>
          <tr>
            <th>shift</th>
            <th>Sun</th>
            <th>longest dark</th>
            <th>Earth</th>
            {earth && <th>longest Earth outage</th>}
          </tr>
        </thead>
        <tbody>
          <ShiftRow label="nominal" metrics={report.nominal} nominal={report.nominal} earth={earth} />
          {report.date_shifts.map((shift) => (
            <ShiftRow
              key={shift.shift_days}
              label={formatShiftDays(shift.shift_days)}
              metrics={shift.metrics}
              nominal={report.nominal}
              earth={earth}
            />
          ))}
        </tbody>
      </table>

      <h4>Where the lander touches down</h4>
      <p>{touchdownVerdict(samples, report.nominal, tab.center)}</p>
      {samples.length > 0 && (
        <>
          <TouchdownFigure samples={samples} nominal={report.nominal} center={tab.center} />
          <table className="rpt-table">
            <thead>
              <tr>
                <th>point</th>
                <th>Sun</th>
                <th>Earth</th>
                <th>landing slope</th>
              </tr>
            </thead>
            <tbody>
              {samples.map((sample, i) => (
                <tr key={i}>
                  <td>
                    {Math.round(sample.offset_m)} m {compass(bearingDeg(tab.center, sample.location))}
                  </td>
                  <td>{formatPercent(sample.metrics.illumination_fraction)}</td>
                  <td>{formatPercent(sample.metrics.earth_visibility_fraction)}</td>
                  <td>{sample.slope_max_deg.toFixed(1)}°</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {earth && (
        <p className="rpt-note">
          Direct-to-Earth link: the Earth is hidden part of the time in at least one case; the longest outage is{' '}
          {formatAtLeast(
            Math.max(...cases.map((m) => m.longest_earth_hidden_h)),
            cases.some((m) => m.longest_earth_hidden_truncated),
          )}
          .
        </p>
      )}
    </div>
  )
}

/** "Mission analysis" section: one block per analysis tab with a report, in the order of the analysis window. */
export function MissionAnalysis(props: MissionAnalysisSectionProps) {
  const { data, sites, number } = props
  return (
    <section className="rpt-section">
      <h2>{number}. Mission analysis</h2>
      <p className="rpt-note">
        Robustness of each analyzed site to launch slips (the window shifted by the listed days; +29.5 d is one lunar
        cycle) and to where the lander actually touches down (points inside the landing-precision disk). Values come
        from the engine (JPL Horizons ephemerides, LOLA terrain); the AI comment only quotes them.
      </p>
      {data.map((tab) => (
        <TabReport key={tab.id} tab={tab} sites={sites} />
      ))}
    </section>
  )
}
