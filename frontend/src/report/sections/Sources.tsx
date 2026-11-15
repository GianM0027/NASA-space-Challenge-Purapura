// ABOUTME: Report section listing data sources and methods (UI-13, D42), taken from the results when available
// ABOUTME: Owner: Federico. Static HTML only

import type { SectionProps, SourcesData } from '../types'

export function Sources({ data, number }: SectionProps<SourcesData>) {
  const terrain = data.evaluation?.terrain
  const horizon = data.evaluation?.horizon
  return (
    <section className="rpt-section">
      <h2>{number}. Sources and methods</h2>
      <ul className="rpt-list">
        <li>
          Terrain: LRO LOLA gridded elevation models (PDS LRO-L-LOLA-4-GDR-V1.0): LDEM_64 global, LDEM_80S_80M and
          LDEM_85S_20M south polar (decisions D28, D31).
          {terrain && ` This site: slopes from ${terrain.dem_source}.`}
        </li>
        {horizon && (
          <li>
            Terrain horizon: {horizon.azimuth_deg.length} azimuths, rays to {(horizon.max_distance_m / 1000).toFixed(0)} km
            from {horizon.dem_source}, Moon curvature included.
          </li>
        )}
        <li>
          Sun and Earth positions: JPL Horizons ephemerides; a body counts as visible when its center is above the
          terrain horizon at its azimuth.
        </li>
        <li>Reference sphere radius 1737.4 km; slopes on a 100 m baseline, maxima as the 99th percentile (D36).</li>
        {data.tradeoff && <li>Trade-off: {data.tradeoff.method}</li>}
      </ul>
    </section>
  )
}
