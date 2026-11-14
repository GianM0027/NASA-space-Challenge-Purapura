// ABOUTME: Site panel (spec UI-2): time window controls, power and communication metrics of a point
// ABOUTME: Owner: Gian. Shows numbers from Evaluation only; the elevation timeline is a separate component

import type { Evaluation, GeoPoint } from '../api/contracts'
import {
  formatAtLeast,
  formatCoordinates,
  formatDuration,
  formatPercent,
  formatUtc,
  hoursBetween,
} from '../format'

export type WindowSettings = { durationDays: number; stepMinutes: number }

type Props = {
  title: string | null
  location: GeoPoint | null
  settings: WindowSettings
  onSettings: (settings: WindowSettings) => void
  evaluation: Evaluation | null
  loading: boolean
  error: string | null
}

const DURATIONS = [1, 7, 14, 30, 60]
const STEPS = [10, 30, 60, 240]

/** One "time to next event" line, relative to the window start. */
function NextEvent(props: { label: string; startUtc: string; eventUtc: string | null | undefined }) {
  const { label, startUtc, eventUtc } = props
  return (
    <div className="event">
      <span className="event-label">{label}</span>
      {eventUtc ? (
        <>
          <strong>in {formatDuration(hoursBetween(startUtc, eventUtc))}</strong>
          <span className="muted">{formatUtc(eventUtc)}</span>
        </>
      ) : (
        <span className="muted">not within the window</span>
      )}
    </div>
  )
}

function Metric(props: { label: string; value: string }) {
  return (
    <div className="metric">
      <span className="metric-value">{props.value}</span>
      <span className="metric-label">{props.label}</span>
    </div>
  )
}

/** Window controls plus the metrics of the selected point. */
export function SitePanel(props: Props) {
  const { title, location, settings, onSettings, evaluation, loading, error } = props
  if (!location) {
    return (
      <section className="panel">
        <h2>Site</h2>
        <p className="muted">Pick a site marker or click anywhere on the globe.</p>
      </section>
    )
  }
  const metrics = evaluation?.metrics
  const start = evaluation?.window.start_utc
  return (
    <section className="panel">
      <h2>{title ?? 'Custom location'}</h2>
      <p className="muted">{formatCoordinates(location)}</p>

      <div className="controls">
        <label>
          Window
          <select
            value={settings.durationDays}
            onChange={(event) =>
              onSettings({ ...settings, durationDays: Number(event.target.value) })
            }
          >
            {DURATIONS.map((days) => (
              <option key={days} value={days}>
                {days} d
              </option>
            ))}
          </select>
        </label>
        <label>
          Step
          <select
            value={settings.stepMinutes}
            onChange={(event) =>
              onSettings({ ...settings, stepMinutes: Number(event.target.value) })
            }
          >
            {STEPS.map((minutes) => (
              <option key={minutes} value={minutes}>
                {minutes} min
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && <p className="error">{error}</p>}
      {loading && !evaluation && <p className="muted">Evaluating...</p>}

      {evaluation && metrics && start && (
        <div className={loading ? 'stale' : undefined}>
          <h3>Power (Sun)</h3>
          <NextEvent
            label={metrics.sun_visible_at_start ? 'Sunset' : 'Sunrise'}
            startUtc={start}
            eventUtc={metrics.sun_visible_at_start ? metrics.next_sunset_utc : metrics.next_sunrise_utc}
          />
          <div className="metrics">
            <Metric label="time in sunlight" value={formatPercent(metrics.illumination_fraction)} />
            <Metric
              label="longest light"
              value={formatAtLeast(metrics.longest_light_h, metrics.longest_light_truncated)}
            />
            <Metric
              label="longest dark"
              value={formatAtLeast(metrics.longest_dark_h, metrics.longest_dark_truncated)}
            />
            <Metric
              label="max Sun elevation"
              value={`${metrics.sun_elevation_max_deg.toFixed(1)}°`}
            />
          </div>

          <h3>Power and link together</h3>
          <div className="metrics">
            <Metric
              label="time with Sun and Earth both visible"
              value={formatPercent(metrics.sun_and_earth_visible_fraction)}
            />
          </div>

          <h3>Communication (Earth)</h3>
          <NextEvent
            label={metrics.earth_visible_at_start ? 'Earthset' : 'Earthrise'}
            startUtc={start}
            eventUtc={
              metrics.earth_visible_at_start ? metrics.next_earthset_utc : metrics.next_earthrise_utc
            }
          />
          <div className="metrics">
            <Metric
              label="time with Earth visible"
              value={formatPercent(metrics.earth_visibility_fraction)}
            />
            <Metric
              label="longest contact"
              value={formatAtLeast(
                metrics.longest_earth_visible_h,
                metrics.longest_earth_visible_truncated,
              )}
            />
            <Metric
              label="longest outage"
              value={formatAtLeast(
                metrics.longest_earth_hidden_h,
                metrics.longest_earth_hidden_truncated,
              )}
            />
            <Metric
              label="mean Earth elevation when visible"
              value={
                metrics.earth_elevation_mean_visible_deg === null
                  ? 'n/a'
                  : `${metrics.earth_elevation_mean_visible_deg.toFixed(1)}°`
              }
            />
          </div>

          <h3>Terrain</h3>
          <p className="muted small">
            Regional slopes, measured over a {Math.round(evaluation.terrain.dem_resolution_m)} m
            baseline (one elevation-model pixel); not lander-scale.
          </p>
          <div className="metrics">
            <Metric label="max slope" value={`${evaluation.terrain.slope_max_deg.toFixed(1)}°`} />
            <Metric label="mean slope" value={`${evaluation.terrain.slope_mean_deg.toFixed(1)}°`} />
            <Metric label="elevation" value={`${Math.round(evaluation.terrain.elevation_m)} m`} />
          </div>
          <p className="muted small">
            Horizon: {evaluation.horizon.dem_source}. {evaluation.times_utc.length} samples from{' '}
            {formatUtc(start)}. A ≥ marks a period cut by the window: it may last longer.
          </p>
        </div>
      )}
    </section>
  )
}
