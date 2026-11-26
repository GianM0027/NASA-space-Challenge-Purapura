// ABOUTME: Admin "Site version" panel (decision D46): live vs latest version, what changed, update button
// ABOUTME: Owner: Gian. The server runs the deploy; this panel polls and reloads when the new version is live

import { useCallback, useEffect, useState } from 'react'
import { api, type SiteUpdateStatus } from '../api/client'
import { accountError } from './errors'

const POLL_MS = 4000

function short(sha: string | undefined | null): string {
  return sha ? sha.slice(0, 7) : '?'
}

function when(iso: string | null | undefined): string {
  if (!iso) return ''
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
}

export function SiteUpdatePanel() {
  const [status, setStatus] = useState<SiteUpdateStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  // The commit being deployed: when it is live, the page reloads to pick up the new frontend.
  const [target, setTarget] = useState<string | null>(null)

  const load = useCallback(() => {
    api
      .siteUpdateStatus()
      .then((next) => {
        setStatus(next)
        setError(null)
        if (target && next.live?.sha === target && next.state === 'idle') location.reload()
      })
      // During the restart the API answers 503 for a few seconds: keep the last status.
      .catch((reason: unknown) => {
        if (!target) setError(accountError(reason))
      })
  }, [target])

  // First check when the panel opens (later checks: the button, or polling while updating).
  useEffect(() => {
    api.siteUpdateStatus().then(setStatus).catch((reason: unknown) => setError(accountError(reason)))
  }, [])

  const updating = status?.state === 'requested' || status?.state === 'running' || target !== null
  useEffect(() => {
    if (!updating) return
    const timer = setInterval(load, POLL_MS)
    return () => clearInterval(timer)
  }, [updating, load])

  async function update() {
    setBusy(true)
    setError(null)
    try {
      const next = await api.requestSiteUpdate()
      setTarget(next.latest?.sha ?? null)
      setStatus(next)
    } catch (reason) {
      setError(accountError(reason))
    } finally {
      setBusy(false)
    }
  }

  if (error && !status) return <p className="error small">{error}</p>
  if (!status) return <p className="muted small">Checking…</p>
  if (!status.enabled) return <p className="muted small">{status.message}</p>

  return (
    <div className="site-update">
      <p className="small">
        Live: <code>{short(status.live?.sha)}</code>
        {status.deployed_at && <span className="muted"> · {when(status.deployed_at)}</span>}
        <br />
        Latest on GitHub: <code>{short(status.latest?.sha)}</code>
        {status.latest?.title && <span className="muted"> · {status.latest.title}</span>}
      </p>

      {updating ? (
        <p className="small site-update-progress" role="status">
          <span className="spinner" aria-hidden="true" /> Updating: tests, build, then a short maintenance page. This page
          reloads by itself when the new version is live.
        </p>
      ) : status.update_available ? (
        <>
          {status.changes.length > 0 && (
            <>
              <p className="small">New since the live version:</p>
              <ul className="site-update-changes small">
                {status.changes.map((change, i) => (
                  <li key={i}>{change}</li>
                ))}
              </ul>
            </>
          )}
          <button className="primary" disabled={busy} onClick={() => void update()}>
            {busy ? 'Requesting…' : 'Update the site'}
          </button>
        </>
      ) : (
        <div className="row">
          <span className="small">{status.latest ? 'No changes available right now.' : ''}</span>
          <button onClick={load}>Check again</button>
        </div>
      )}

      {status.state === 'failed' && !updating && <p className="error small">Last update failed: {status.message}</p>}
      {status.message && status.state !== 'failed' && !updating && <p className="muted small">{status.message}</p>}
      {error && <p className="error small">{error}</p>}
    </div>
  )
}
