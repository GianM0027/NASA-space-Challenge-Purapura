// ABOUTME: Data sources and attribution (spec UI-6): a short credit line with a small popover
// ABOUTME: Owner: Gian. Mirrors spec section 7; per-site coordinate sources stay in the site panel

import { useState } from 'react'

type DataSource = { what: string; provider: string; use: string; url?: string }

/** The data the app shows, as listed in spec section 7 plus the requirement sources. */
const SOURCES: DataSource[] = [
  {
    what: 'LRO WAC global mosaic',
    provider: 'NASA / GSFC / ASU, via NASA Moon Trek',
    use: 'globe texture',
    url: 'https://trek.nasa.gov/moon/',
  },
  {
    what: 'LOLA gridded elevation models (LDEM_64, LDEM_80S_80M, LDEM_85S_20M)',
    provider: 'NASA LRO LOLA, PDS Geosciences Node',
    use: 'terrain horizon, slopes',
    url: 'https://pds-geosciences.wustl.edu/missions/lro/lola.htm',
  },
  {
    what: 'JPL Horizons',
    provider: 'NASA JPL',
    use: 'Sun and Earth directions from each site',
    url: 'https://ssd-api.jpl.nasa.gov/doc/horizons.html',
  },
  {
    what: 'Human Landing System Overview (2025)',
    provider: 'NASA',
    use: 'landing slope limit (10° over 100 m), landing precision (100 m)',
  },
  {
    what: 'Landing site coordinates, mission types, named regions',
    provider: 'cited per entry (site panel, docs/domain)',
    use: 'catalog, AI defaults and search scope',
  },
  {
    what: 'Claude (Anthropic)',
    provider: 'Claude Code CLI',
    use: 'reads requests and writes comments; every number comes from the engine and is checked',
  },
]

/** A short credit for the legend; the full list opens in a small popover above it. */
export function DataSources() {
  const [open, setOpen] = useState(false)
  return (
    <span className="data-sources">
      <button className="link muted" title="Data sources and attribution" onClick={() => setOpen(!open)}>
        Data: NASA LRO · LOLA · JPL Horizons ⓘ
      </button>
      {open && (
        <div className="data-sources-popover" role="dialog" aria-label="Data sources">
          <ul>
            {SOURCES.map((source) => (
              <li key={source.what}>
                {source.url ? (
                  <a href={source.url} target="_blank" rel="noreferrer">
                    {source.what}
                  </a>
                ) : (
                  source.what
                )}
                <span className="muted">
                  {' '}
                  · {source.provider} · {source.use}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </span>
  )
}
