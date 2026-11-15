// ABOUTME: Dev-only entry of the comparison view preview: loads the sites, mounts CompareView like the App dock
// ABOUTME: Owner: Federico (D37). Not part of the app bundle; the app mounts CompareView from App (Gian)

import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import '../index.css'
import { api } from '../api/client'
import type { Site } from '../api/contracts'
import { CompareView } from './CompareView'

// oxlint-disable-next-line react/only-export-components -- dev-only entry, never hot-reloaded as a module
function Preview() {
  const [sites, setSites] = useState<Site[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    api.sites().then(setSites).catch((reason: unknown) => setError(String(reason)))
  }, [])
  const start = new Date('2026-11-14T00:00:00Z')
  const window = {
    start_utc: start.toISOString(),
    end_utc: new Date(start.getTime() + 30 * 24 * 3_600_000).toISOString(),
    step_minutes: 60,
  }
  if (error) return <p className="error banner">{error}</p>
  if (!sites) return <p className="banner">Loading sites…</p>
  return (
    <div style={{ position: 'fixed', left: 12, bottom: 44 }}>
      <CompareView sites={sites} defaultWindow={window} initialSiteId="im-2" />
    </div>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Preview />
  </StrictMode>,
)
