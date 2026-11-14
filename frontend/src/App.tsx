// ABOUTME: Root component of the LunarNav frontend; for now a connectivity check against the backend
// ABOUTME: Owner: Gian. Replaced by the map, site panel and AI box (spec UI-1, UI-2, UI-4)

import { useEffect, useState } from 'react'

type SiteSummary = { id: string; name: string }

type Status =
  | { kind: 'loading' }
  | { kind: 'ok'; sites: SiteSummary[] }
  | { kind: 'error'; message: string }

/** Shows whether the backend answers and lists the catalog sites it returns. */
function App() {
  const [status, setStatus] = useState<Status>({ kind: 'loading' })

  useEffect(() => {
    fetch('/api/sites')
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        setStatus({ kind: 'ok', sites: (await response.json()) as SiteSummary[] })
      })
      .catch((error: unknown) => setStatus({ kind: 'error', message: String(error) }))
  }, [])

  return (
    <main>
      <h1>LunarNav</h1>
      {status.kind === 'loading' && <p>Connecting to the backend...</p>}
      {status.kind === 'error' && <p>Backend unreachable: {status.message}</p>}
      {status.kind === 'ok' && (
        <ul>
          {status.sites.map((site) => (
            <li key={site.id}>{site.name}</li>
          ))}
        </ul>
      )}
    </main>
  )
}

export default App
