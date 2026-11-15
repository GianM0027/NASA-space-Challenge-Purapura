// ABOUTME: Report section of the last site evaluation (UI-13, D42): lighting, Earth link, terrain, visibility strip
// ABOUTME: Owner: Federico. Values come straight from the Evaluation contract; static HTML and SVG only

import type { Evaluation } from '../../api/contracts'
import { formatAtLeast, formatCoordinates, formatPercent, formatUtc } from '../../format'
import { visibleRuns } from '../series'
import type { SectionProps, SiteSectionData } from '../types'

/** Two strips over the window: when the Sun and when the Earth stand above the terrain horizon. */
function VisibilityStrip({ evaluation }: { evaluation: Evaluation }) {
  const n = evaluation.times_utc.length
  if (n < 2) return null
  const width = 600
  const rows: [string, boolean[], string][] = [
    ['Sun', evaluation.sun_visible, '#e0a800'],
    ['Earth', evaluation.earth_visible, '#2f6fde'],
  ]
  const x = (k: number) => 50 + (k / n) * (width - 50)
  return (
    <figure className="rpt-figure">
      <svg viewBox={`0 0 ${width} 62`} role="img" aria-label="Sun and Earth visibility over the window">
        {rows.map(([label, visible, color], r) => (
          <g key={label} transform={`translate(0 ${r * 24})`}>
            <text x={0} y={14} fontSize={11}>
              {label}
            </text>
            <rect x={50} y={3} width={width - 50} height={14} fill="#eceef2" />
            {visibleRuns(visible).map(([a, b]) => (
              <rect key={a} x={x(a)} y={3} width={Math.max(x(b) - x(a), 0.5)} height={14} fill={color} />
            ))}
          </g>
        ))}
        <text x={50} y={60} fontSize={9}>
          {formatUtc(evaluation.times_utc[0])}
        </text>
        <text x={width} y={60} fontSize={9} textAnchor="end">
          {formatUtc(evaluation.times_utc[n - 1])}
        </text>
      </svg>
      <figcaption>Colored: body above the terrain horizon (visible); grey: hidden.</figcaption>
    </figure>
  )
}

export function SiteEvaluation({ data, sites, number }: SectionProps<SiteSectionData>) {
  const m = data.metrics
  const t = data.terrain
  const site = sites.find((s) => s.id === data.site_id)
  return (
    <section className="rpt-section">
      <h2>
        {number}. Site evaluation: {site?.name ?? 'custom point'}
      </h2>
      <dl className="rpt-kv">
        <dt>Location</dt>
        <dd>{formatCoordinates(data.location)}</dd>
        <dt>Window</dt>
        <dd>
          {formatUtc(data.window.start_utc)} to {formatUtc(data.window.end_utc)}, every {data.window.step_minutes} min
        </dd>
        <dt>Operations area</dt>
        <dd>
          landing precision {data.area.landing_precision_m} m, rover range {data.area.operating_range_m} m, max rover slope{' '}
          {data.area.traverse_slope_limit_deg}°, panel height {data.area.observer_height_above_ground_m} m
        </dd>
      </dl>

      <VisibilityStrip evaluation={data} />

      <table className="rpt-table">
        <thead>
          <tr>
            <th>Quantity</th>
            <th>Sun</th>
            <th>Earth</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Time visible</td>
            <td>{formatPercent(m.illumination_fraction)}</td>
            <td>{formatPercent(m.earth_visibility_fraction)}</td>
          </tr>
          <tr>
            <td>Longest visible run</td>
            <td>{formatAtLeast(m.longest_light_h, m.longest_light_truncated)}</td>
            <td>{formatAtLeast(m.longest_earth_visible_h, m.longest_earth_visible_truncated)}</td>
          </tr>
          <tr>
            <td>Longest hidden run</td>
            <td>{formatAtLeast(m.longest_dark_h, m.longest_dark_truncated)}</td>
            <td>{formatAtLeast(m.longest_earth_hidden_h, m.longest_earth_hidden_truncated)}</td>
          </tr>
          <tr>
            <td>Mean elevation while visible</td>
            <td>{m.sun_elevation_mean_visible_deg === null ? 'n/a' : `${m.sun_elevation_mean_visible_deg.toFixed(1)}°`}</td>
            <td>{m.earth_elevation_mean_visible_deg === null ? 'n/a' : `${m.earth_elevation_mean_visible_deg.toFixed(1)}°`}</td>
          </tr>
        </tbody>
      </table>
      <p className="rpt-note">
        Sun and Earth visible together: {formatPercent(m.sun_and_earth_visible_fraction)} of the window. "≥" marks a run
        that touches the window edge, so it may be longer.
      </p>

      <table className="rpt-table">
        <thead>
          <tr>
            <th>Terrain</th>
            <th>Value</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Elevation (1737.4 km sphere)</td>
            <td>{t.elevation_m.toFixed(0)} m</td>
          </tr>
          <tr>
            <td>Landing slope, within {t.landing_radius_m} m (mean / P99)</td>
            <td>
              {t.landing_slope_mean_deg.toFixed(1)}° / {t.landing_slope_max_deg.toFixed(1)}°
            </td>
          </tr>
          <tr>
            <td>Slope, within {t.radius_m} m (mean / P99)</td>
            <td>
              {t.slope_mean_deg.toFixed(1)}° / {t.slope_max_deg.toFixed(1)}°
            </td>
          </tr>
          <tr>
            <td>Reachable area at ≤ {t.traverse_slope_limit_deg}°</td>
            <td>{t.reachable_fraction === null ? 'n/a (no rover range)' : formatPercent(t.reachable_fraction)}</td>
          </tr>
        </tbody>
      </table>
    </section>
  )
}
