// ABOUTME: Root of the LunarNav frontend: globe, date control, site list and site panel, module status
// ABOUTME: Owner: Gian. Holds the selection and the time window; children are presentational

import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, type ModuleStatus } from './api/client'
import type { Evaluation, GeoPoint, Site, SkyState } from './api/contracts'
import { formatUtc, fromInputValue, toInputValue } from './format'
import { MoonGlobe, type GlobeFocus } from './globe/MoonGlobe'
import { MOON_TEXTURE_ATTRIBUTION } from './globe/moonTexture'
import { SitePanel, type WindowSettings } from './panels/SitePanel'

/** What is being evaluated: a catalog site or a point picked on the globe. */
type Target = { siteId: string } | { location: GeoPoint }

const VIEWS: { label: string; lat: number; lon: number }[] = [
  { label: 'Near side', lat: 0, lon: 0 },
  { label: 'Far side', lat: 0, lon: 180 },
  { label: 'North pole', lat: 90, lon: 0 },
  { label: 'South pole', lat: -90, lon: 0 },
]

/** Result of one evaluation request, tagged with the request it answers. */
type Outcome = { key: string; evaluation: Evaluation | null; error: string | null }

/** Today at 00:00 UTC, as an ISO instant. */
function todayUtc(): string {
  return `${new Date().toISOString().slice(0, 10)}T00:00:00.000Z`
}

function App() {
  const [modules, setModules] = useState<ModuleStatus>({})
  const [sites, setSites] = useState<Site[]>([])
  const [bootError, setBootError] = useState<string | null>(null)
  const [startUtc, setStartUtc] = useState(todayUtc)
  const [sky, setSky] = useState<SkyState | null>(null)
  const [uniformLight, setUniformLight] = useState(false)
  const [focus, setFocus] = useState<GlobeFocus | null>(null)
  const [target, setTarget] = useState<Target | null>(null)
  const [settings, setSettings] = useState<WindowSettings>({ durationDays: 30, stepMinutes: 60 })
  const [outcome, setOutcome] = useState<Outcome | null>(null)

  useEffect(() => {
    Promise.all([api.modules(), api.sites()])
      .then(([moduleStatus, siteList]) => {
        setModules(moduleStatus)
        setSites(siteList)
      })
      .catch((reason: unknown) => setBootError(String(reason)))
  }, [])

  useEffect(() => {
    let current = true
    api
      .sky(startUtc)
      .then((state) => current && setSky(state))
      .catch(() => current && setSky(null))
    return () => {
      current = false
    }
  }, [startUtc])

  // Identifies the current evaluation request; an outcome with another key is stale.
  const requestKey = target ? JSON.stringify([target, startUtc, settings]) : null

  useEffect(() => {
    if (!target || !requestKey) return
    let current = true
    const end = new Date(new Date(startUtc).getTime() + settings.durationDays * 86_400_000)
    api
      .evaluate({
        ...('siteId' in target ? { site_id: target.siteId } : { location: target.location }),
        window: {
          start_utc: startUtc,
          end_utc: end.toISOString(),
          step_minutes: settings.stepMinutes,
        },
      })
      .then((evaluation) => current && setOutcome({ key: requestKey, evaluation, error: null }))
      .catch((reason: unknown) => {
        if (current) setOutcome({ key: requestKey, evaluation: null, error: String(reason) })
      })
    return () => {
      current = false
    }
  }, [target, startUtc, settings, requestKey])

  const loading = requestKey !== null && outcome?.key !== requestKey

  const selectedSite = useMemo(
    () => (target && 'siteId' in target ? sites.find((site) => site.id === target.siteId) : null),
    [target, sites],
  )
  const selectedLocation =
    selectedSite?.location ?? (target && 'location' in target ? target.location : null)

  const pickSite = useCallback(
    (siteId: string) => {
      setTarget({ siteId })
      const site = sites.find((candidate) => candidate.id === siteId)
      if (site) {
        setFocus({ lat_deg: site.location.lat_deg, lon_deg: site.location.lon_deg, nonce: Date.now() })
      }
    },
    [sites],
  )
  const pickLocation = useCallback((location: GeoPoint) => setTarget({ location }), [])

  const placeholders = Object.entries(modules).filter(([, status]) => status !== 'real')

  return (
    <div className="app">
      <header>
        <h1>LunarNav</h1>
        <div className="modules" title="Which engine modules are live (GET /api/modules)">
          {Object.entries(modules).map(([name, status]) => (
            <span
              key={name}
              className={`badge ${status === 'real' ? 'real' : status === 'example' ? 'example' : 'failed'}`}
              title={status}
            >
              {name}
            </span>
          ))}
        </div>
      </header>

      {bootError && <p className="error banner">Backend unreachable: {bootError}</p>}
      {placeholders.length > 0 && (
        <p className="banner">
          Placeholder data for: {placeholders.map(([name]) => name).join(', ')}. Numbers are not
          real until these modules are live.
        </p>
      )}

      <main>
        <div className="stage">
          <MoonGlobe
            sites={sites}
            selected={selectedLocation}
            sky={sky}
            uniformLight={uniformLight}
            focus={focus}
            onPickSite={pickSite}
            onPickLocation={pickLocation}
          />
          <div className="toolbar">
            <label>
              Date (UTC)
              <input
                type="datetime-local"
                value={toInputValue(startUtc)}
                onChange={(event) => event.target.value && setStartUtc(fromInputValue(event.target.value))}
              />
            </label>
            {VIEWS.map((view) => (
              <button
                key={view.label}
                onClick={() => setFocus({ lat_deg: view.lat, lon_deg: view.lon, nonce: Date.now() })}
              >
                {view.label}
              </button>
            ))}
            <label className="check">
              <input
                type="checkbox"
                checked={uniformLight}
                onChange={(event) => setUniformLight(event.target.checked)}
              />
              Uniform light
            </label>
          </div>
          <div className="legend">
            <span>
              <i className="dot earth" /> Earth direction
            </span>
            <span>
              <i className="dot landed" /> landed
            </span>
            <span>
              <i className="dot planned" /> planned
            </span>
            <span>
              <i className="dot candidate" /> candidate
            </span>
            <span>
              <i className="dot custom" /> custom
            </span>
            <span className="muted">
              {sky ? `Sunlight at ${formatUtc(sky.time_utc)}` : 'Sun direction unavailable'}
            </span>
            <span className="muted">{MOON_TEXTURE_ATTRIBUTION}</span>
          </div>
        </div>

        <aside>
          <section className="panel">
            <h2>Sites</h2>
            <ul className="sites">
              {sites.map((site) => (
                <li key={site.id}>
                  <button
                    className={selectedSite?.id === site.id ? 'active' : undefined}
                    onClick={() => pickSite(site.id)}
                  >
                    <i className={`dot ${site.status}`} />
                    {site.name}
                    {site.mission && <span className="muted"> {site.mission}</span>}
                  </button>
                </li>
              ))}
            </ul>
          </section>
          <SitePanel
            title={selectedSite?.name ?? null}
            location={selectedLocation}
            settings={settings}
            onSettings={setSettings}
            evaluation={outcome?.evaluation ?? null}
            loading={loading}
            error={loading ? null : (outcome?.error ?? null)}
          />
        </aside>
      </main>
    </div>
  )
}

export default App
