// ABOUTME: Coordinates box (analyze or save a typed or clicked point) and "My locations" (rename, delete)
// ABOUTME: Owner: Gian. Presentational: the parent makes the API calls and returns an error message or null

import { useState } from 'react'
import type { GeoPoint, Site } from '../api/contracts'
import { formatCoordinates } from '../format'
import { parseCoordinates } from '../sites/userSites'

/** An async action that resolves to an error message to show, or null on success. */
type Action<Args extends unknown[]> = (...args: Args) => Promise<string | null>

/** Coordinates with fixed decimals for the input fields (enough for ~30 m on the Moon). */
function toField(value: number | undefined): string {
  return value === undefined ? '' : String(Number(value.toFixed(4)))
}

/**
 * Typed coordinates, prefilled with the last point clicked on the globe.
 *
 * The parent remounts it (via `key`) when a new point is clicked, so the fields follow the click.
 */
export function CoordinatesBox(props: {
  initial: GeoPoint | null
  onAnalyze: (point: GeoPoint) => void
  onSave: Action<[name: string, description: string, point: GeoPoint]>
}) {
  const { initial, onAnalyze, onSave } = props
  const [lat, setLat] = useState(toField(initial?.lat_deg))
  const [lon, setLon] = useState(toField(initial?.lon_deg))
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  /** Validate the fields; show the problem and return null when they are invalid. */
  function point(): GeoPoint | null {
    const parsed = parseCoordinates(lat, lon)
    if ('error' in parsed) {
      setMessage(parsed.error)
      return null
    }
    setMessage(null)
    return parsed.point
  }

  async function save() {
    const location = point()
    if (!location) return
    setSaving(true)
    const error = await onSave(name, description, location)
    setSaving(false)
    setMessage(error)
    if (!error) {
      setName('')
      setDescription('')
    }
  }

  return (
    <section className="panel">
      <h2>Coordinates</h2>
      <form
        className="controls"
        onSubmit={(event) => {
          event.preventDefault()
          const location = point()
          if (location) onAnalyze(location)
        }}
      >
        <label title="Planetocentric latitude, degrees, -90 to 90">
          Lat
          <input className="num" value={lat} onChange={(e) => setLat(e.target.value)} placeholder="-89.5" />
        </label>
        <label title="East-positive longitude, degrees, -180 to below 180">
          Lon E
          <input className="num" value={lon} onChange={(e) => setLon(e.target.value)} placeholder="45" />
        </label>
        <button type="submit">Analyze</button>
      </form>
      <form
        className="controls"
        onSubmit={(event) => {
          event.preventDefault()
          void save()
        }}
      >
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name (required)" />
        <input
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Description (optional)"
        />
        <button type="submit" disabled={saving}>
          {saving ? 'Saving...' : 'Save as location'}
        </button>
      </form>
      {message && <p className="error">{message}</p>}
    </section>
  )
}

/** One user location: pick, rename inline, delete after an inline confirmation. */
function LocationRow(props: {
  site: Site
  active: boolean
  onPick: (siteId: string) => void
  onRename: Action<[siteId: string, name: string]>
  onDelete: Action<[siteId: string]>
}) {
  const { site, active, onPick, onRename, onDelete } = props
  const [mode, setMode] = useState<'view' | 'rename' | 'confirm'>('view')
  const [draft, setDraft] = useState(site.name)
  const [message, setMessage] = useState<string | null>(null)

  async function rename() {
    if (!draft.trim()) {
      setMessage('The name cannot be empty.')
      return
    }
    setMessage(null)
    // An API error is shown by the section, which outlives this row (e.g. after a 404).
    if (!(await onRename(site.id, draft))) setMode('view')
  }

  async function remove() {
    // On success the row disappears with the refreshed list; errors are shown by the section.
    await onDelete(site.id)
    setMode('view')
  }

  return (
    <li>
      {mode === 'rename' ? (
        <form
          className="row"
          onSubmit={(event) => {
            event.preventDefault()
            void rename()
          }}
        >
          <input
            autoFocus
            value={draft}
            aria-label={`New name for ${site.name}`}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === 'Escape' && setMode('view')}
          />
          <button type="submit">Save</button>
          <button type="button" onClick={() => setMode('view')}>
            Cancel
          </button>
        </form>
      ) : (
        <div className="row">
          <button className={`grow${active ? ' active' : ''}`} onClick={() => onPick(site.id)}>
            <i className="dot custom" />
            {site.name}
            <span className="muted small"> {formatCoordinates(site.location)}</span>
          </button>
          <button
            title="Rename"
            onClick={() => {
              setDraft(site.name)
              setMessage(null)
              setMode('rename')
            }}
          >
            Rename
          </button>
          <button title="Delete" onClick={() => setMode('confirm')}>
            Delete
          </button>
        </div>
      )}
      {mode === 'confirm' && (
        <div className="row confirm">
          <span>Delete '{site.name}'? This cannot be undone.</span>
          <button onClick={() => void remove()}>Delete</button>
          <button onClick={() => setMode('view')}>Cancel</button>
        </div>
      )}
      {message && <p className="error">{message}</p>}
    </li>
  )
}

/** The user's saved locations (`origin == "user"`), separate from the curated sites. */
export function MyLocations(props: {
  sites: Site[]
  selectedId: string | null
  onPick: (siteId: string) => void
  onRename: Action<[siteId: string, name: string]>
  onDelete: Action<[siteId: string]>
}) {
  const { sites, selectedId, onPick, onRename, onDelete } = props
  // The last rename or delete error, kept here because the row it concerns may be gone.
  const [notice, setNotice] = useState<string | null>(null)

  /** Wrap an action so that its outcome replaces the section's notice. */
  function reporting<Args extends unknown[]>(action: Action<Args>): Action<Args> {
    return async (...args) => {
      const error = await action(...args)
      setNotice(error)
      return error
    }
  }

  return (
    <section className="panel">
      <h2>My locations</h2>
      {notice && <p className="error">{notice}</p>}
      {sites.length === 0 ? (
        <p className="muted">None yet: type coordinates or click the globe, then "Save as location".</p>
      ) : (
        <ul className="sites">
          {sites.map((site) => (
            <LocationRow
              key={site.id}
              site={site}
              active={site.id === selectedId}
              onPick={onPick}
              onRename={reporting(onRename)}
              onDelete={reporting(onDelete)}
            />
          ))}
        </ul>
      )}
    </section>
  )
}
