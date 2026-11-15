// ABOUTME: Report cover (UI-13, D42): title, generation time, mission window and table of contents
// ABOUTME: Owner: Federico. Static HTML only, printed through window.print()

import { formatDuration, formatUtc, hoursBetween } from '../../format'
import type { CoverData, SectionProps } from '../types'

export function Cover({ data }: SectionProps<CoverData>) {
  const { window } = data
  return (
    <section className="rpt-section rpt-cover">
      <p className="rpt-kicker">LunarNav · lunar landing site analysis</p>
      <h1>{data.title}</h1>
      <dl className="rpt-kv">
        <dt>Generated</dt>
        <dd>{formatUtc(data.generatedUtc)}</dd>
        <dt>Mission window</dt>
        <dd>
          {formatUtc(window.start_utc)} to {formatUtc(window.end_utc)} ({formatDuration(hoursBetween(window.start_utc, window.end_utc))},
          one sample every {window.step_minutes} min)
        </dd>
      </dl>
      {data.contents.length > 0 && (
        <>
          <h2>Contents</h2>
          <ul className="rpt-contents">
            {data.contents.map((title) => (
              <li key={title}>{title}</li>
            ))}
          </ul>
        </>
      )}
      <p className="rpt-note">
        Conventions: angles in degrees, distances in meters, times in UTC. Selenographic coordinates are planetocentric,
        east-positive longitude, Moon Mean Earth frame; azimuth from local north, clockwise.
      </p>
    </section>
  )
}
