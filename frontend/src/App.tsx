// ABOUTME: Root of the LunarNav frontend: globe, AI box, site lists, coordinates box, site panel, modules
// ABOUTME: Owner: Gian. Holds the selection and the time window; children are presentational

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AiAssistant } from './ai/AiAssistant'
import { MissionAnalysisBox, type AnalysisTab } from './analysis/MissionAnalysisBox'
import { CompareView } from './compare/CompareView'
import { ReportBuilder } from './report/ReportBuilder'
import { api, ApiError, type ModuleStatus } from './api/client'
import type { Evaluation, GeoPoint, Site, SiteRanking, SkyState, TimeWindow, TradeoffResult } from './api/contracts'
import { formatCoordinates, formatUtc, hoursBetween } from './format'
import { MoonGlobe, type GlobeFocus } from './globe/MoonGlobe'
import { CoordinatesBox, MyLocations } from './panels/LocationsPanel'
import { DataSources } from './panels/DataSources'
import { SitePanel, type WindowSettings } from './panels/SitePanel'
import { buildUserSite, describeSiteError } from './sites/userSites'

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

// Location categories in the legend, each a toggle for its markers on the globe (Site.status).
const MARKER_CATEGORIES = ['landed', 'candidate', 'custom'] as const

function App() {
  const [modules, setModules] = useState<ModuleStatus>({})
  const [sites, setSites] = useState<Site[]>([])
  const [bootError, setBootError] = useState<string | null>(null)
  const [sky, setSky] = useState<SkyState | null>(null)
  const [uniformLight, setUniformLight] = useState(false)
  const [focus, setFocus] = useState<GlobeFocus | null>(null)
  const [target, setTarget] = useState<Target | null>(null)
  // Last point clicked on the globe; its nonce remounts the coordinates box with that point.
  const [clicked, setClicked] = useState<{ point: GeoPoint; nonce: number } | null>(null)
  const [settings, setSettings] = useState<WindowSettings>(() => ({
    startUtc: todayUtc(),
    durationHours: 30 * 24,
    stepMinutes: 60,
  }))
  const startUtc = settings.startUtc
  const [outcome, setOutcome] = useState<Outcome | null>(null)

  useEffect(() => {
    Promise.all([api.modules(), api.sites()])
      .then(([moduleStatus, siteList]) => {
        setModules(moduleStatus)
        setSites(siteList)
      })
      .catch((reason: unknown) => setBootError(String(reason)))
  }, [])

  // Time wheel (spec UI-11): the instant shown on the globe, hours after the window start.
  // Keyed by the window, so a new start or duration brings the shown instant back to the start.
  const windowKey = `${startUtc}|${settings.durationHours}`
  const [view, setView] = useState({ key: windowKey, offsetHours: 0 })
  const viewOffsetHours = view.key === windowKey ? view.offsetHours : 0
  const setViewOffsetHours = useCallback(
    (offsetHours: number) => setView({ key: windowKey, offsetHours }),
    [windowKey],
  )
  const viewUtc = useMemo(
    () => new Date(new Date(startUtc).getTime() + viewOffsetHours * 3_600_000).toISOString(),
    [startUtc, viewOffsetHours],
  )

  // At most one sky request in flight: while one runs, only the latest wanted instant waits.
  const skyBusy = useRef(false)
  const skyWanted = useRef<string | null>(null)
  useEffect(() => {
    skyWanted.current = viewUtc
    if (skyBusy.current) return
    skyBusy.current = true
    const run = (time: string) => {
      api
        .sky(time)
        .then((state) => setSky(state))
        .catch(() => setSky(null))
        .finally(() => {
          const next = skyWanted.current
          if (next !== null && next !== time) run(next)
          else skyBusy.current = false
        })
    }
    run(viewUtc)
  }, [viewUtc])

  // Identifies the current evaluation request; an outcome with another key is stale.
  const requestKey = target ? JSON.stringify([target, settings]) : null

  useEffect(() => {
    if (!target || !requestKey) return
    let current = true
    const end = new Date(new Date(startUtc).getTime() + settings.durationHours * 3_600_000)
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
  }, [target, startUtc, settings.durationHours, settings.stepMinutes, requestKey])

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
  // A ranked site is shown over the mission window the ranking used, not the panel's own.
  const pickRanked = useCallback(
    (siteId: string, window: TimeWindow | null) => {
      pickSite(siteId)
      if (window) {
        setSettings({
          startUtc: new Date(window.start_utc).toISOString(),
          durationHours: Math.round(hoursBetween(window.start_utc, window.end_utc)),
          stepMinutes: window.step_minutes,
        })
      }
    },
    [pickSite],
  )
  const pickLocation = useCallback((location: GeoPoint) => {
    setTarget({ location })
    setClicked({ point: location, nonce: Date.now() })
  }, [])
  // Typed coordinates are evaluated exactly like a globe click (site_id null).
  const analyzePoint = useCallback((location: GeoPoint) => {
    setTarget({ location })
    setFocus({ lat_deg: location.lat_deg, lon_deg: location.lon_deg, nonce: Date.now() })
  }, [])

  const refreshSites = useCallback(async () => {
    try {
      setSites(await api.sites())
    } catch (reason: unknown) {
      setBootError(String(reason))
    }
  }, [])

  const saveLocation = useCallback(
    async (name: string, description: string, location: GeoPoint): Promise<string | null> => {
      const built = buildUserSite(name, location, description)
      if ('error' in built) return built.error
      try {
        const saved = await api.addSite(built.site)
        await refreshSites()
        setTarget({ siteId: saved.id })
        return null
      } catch (reason: unknown) {
        return describeSiteError(reason, built.site.id)
      }
    },
    [refreshSites],
  )

  const editLocation = useCallback(
    async (siteId: string, name: string, description: string): Promise<string | null> => {
      try {
        await api.updateSite(siteId, { name, description })
        await refreshSites()
        return null
      } catch (reason: unknown) {
        if (reason instanceof ApiError && reason.status === 404) await refreshSites()
        return describeSiteError(reason, siteId)
      }
    },
    [refreshSites],
  )

  const deleteLocation = useCallback(
    async (siteId: string): Promise<string | null> => {
      const clearIfShown = () =>
        setTarget((current) => (current && 'siteId' in current && current.siteId === siteId ? null : current))
      try {
        await api.removeSite(siteId)
        clearIfShown()
        await refreshSites()
        return null
      } catch (reason: unknown) {
        if (reason instanceof ApiError && reason.status === 404) {
          clearIfShown()
          await refreshSites()
        }
        return describeSiteError(reason, siteId)
      }
    },
    [refreshSites],
  )

  const curatedSites = useMemo(() => sites.filter((site) => site.origin !== 'user'), [sites])
  const userSites = useMemo(() => sites.filter((site) => site.origin === 'user'), [sites])

  const placeholders = Object.entries(modules).filter(([, status]) => status !== 'real')

  // Marker categories hidden on the globe from the legend; the side lists keep every location.
  const [hiddenCategories, setHiddenCategories] = useState<string[]>([])
  const globeSites = useMemo(
    () => sites.filter((site) => !hiddenCategories.includes(site.status)),
    [sites, hiddenCategories],
  )

  // Latest AI ranking and trade-off of the session, printed by the PDF report (decision D42).
  const [lastRanking, setLastRanking] = useState<SiteRanking | null>(null)
  const [lastTradeoff, setLastTradeoff] = useState<TradeoffResult | null>(null)

  // Mission analysis window (spec UI-5): one tab per site and window, kept until closed or reset.
  const [analyses, setAnalyses] = useState<AnalysisTab[]>([])
  const [activeAnalysis, setActiveAnalysis] = useState<string | null>(null)
  const [analysesMinimized, setAnalysesMinimized] = useState(false)
  const updateAnalysis = useCallback(
    (id: string, update: Partial<AnalysisTab>) =>
      setAnalyses((tabs) => tabs.map((tab) => (tab.id === id ? { ...tab, ...update } : tab))),
    [],
  )
  const closeAnalysis = useCallback((id: string) => {
    setAnalyses((tabs) => tabs.filter((tab) => tab.id !== id))
    setActiveAnalysis((active) => (active === id ? null : active))
  }, [])

  // The window of the site panel is also the AI's default when a request gives no dates.
  const panelWindow: TimeWindow = useMemo(
    () => ({
      start_utc: startUtc,
      end_utc: new Date(new Date(startUtc).getTime() + settings.durationHours * 3_600_000).toISOString(),
      step_minutes: settings.stepMinutes,
    }),
    [startUtc, settings.durationHours, settings.stepMinutes],
  )

  const startAnalysis = useCallback(
    (landingPrecisionM: number) => {
      if (!target || !selectedLocation) return
      const center = selectedLocation
      const id = JSON.stringify([target, panelWindow, landingPrecisionM])
      setActiveAnalysis(id)
      setAnalysesMinimized(false)
      if (analyses.some((tab) => tab.id === id)) return
      const label =
        selectedSite?.name ?? formatCoordinates(center)
      setAnalyses((tabs) => [
        ...tabs,
        { id, label, window: panelWindow, landingPrecisionM, center, report: null, commentDone: false, error: null },
      ])
      api
        .missionAnalysis({
          ...('siteId' in target ? { site_id: target.siteId } : { location: target.location }),
          window: panelWindow,
          area: { landing_precision_m: landingPrecisionM },
        })
        .then((report) => {
          updateAnalysis(id, { report })
          return api
            .commentAnalysis({ report, site_name: label })
            .then((commented) => updateAnalysis(id, { report: commented, commentDone: true }))
            .catch(() => updateAnalysis(id, { commentDone: true }))
        })
        .catch((reason: unknown) => updateAnalysis(id, { error: String(reason) }))
    },
    [target, panelWindow, analyses, selectedSite, selectedLocation, updateAnalysis],
  )

  return (
    <div className="app">
      <header>
        <h1>LunarNav</h1>
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
            sites={globeSites}
            selected={selectedLocation}
            sky={sky}
            uniformLight={uniformLight}
            focus={focus}
            onPickSite={pickSite}
            onPickLocation={pickLocation}
          />
          <div className="toolbar">
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
            {MARKER_CATEGORIES.map((category) => {
              const shown = !hiddenCategories.includes(category)
              return (
                <button
                  key={category}
                  className={shown ? 'legend-toggle' : 'legend-toggle off'}
                  aria-pressed={shown}
                  title={shown ? `Hide ${category} landing sites on the globe` : `Show ${category} landing sites on the globe`}
                  onClick={() =>
                    setHiddenCategories((hidden) =>
                      shown ? [...hidden, category] : hidden.filter((item) => item !== category),
                    )
                  }
                >
                  <i className={`dot ${category}`} /> {category}
                </button>
              )
            })}
            <span className="muted">
              {sky ? `Sunlight at ${formatUtc(sky.time_utc)}` : 'Sun direction unavailable'}
            </span>
            <DataSources />
          </div>
          <div className="dock">
            <AiAssistant sites={sites} defaultWindow={panelWindow} onPickSite={pickRanked} onRanking={setLastRanking} />
            <CompareView
              sites={sites}
              defaultWindow={panelWindow}
              initialSiteId={selectedSite?.id ?? null}
              onResult={setLastTradeoff}
            />
            <ReportBuilder
              sites={sites}
              window={panelWindow}
              evaluation={outcome?.evaluation ?? null}
              analyses={analyses}
              ranking={lastRanking}
              tradeoff={lastTradeoff}
            />
            <MissionAnalysisBox
              tabs={analyses}
              activeId={activeAnalysis}
              minimized={analysesMinimized}
              onSelect={setActiveAnalysis}
              onClose={closeAnalysis}
              onReset={() => setAnalyses([])}
              onMinimize={setAnalysesMinimized}
            />
          </div>
        </div>

        <aside>
          <section className="panel">
            <h2>Preloaded landing sites</h2>
            <ul className="sites">
              {curatedSites.map((site) => (
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
          <MyLocations
            sites={userSites}
            selectedId={selectedSite?.id ?? null}
            onPick={pickSite}
            onEdit={editLocation}
            onDelete={deleteLocation}
          />
          <CoordinatesBox
            key={clicked?.nonce ?? 0}
            initial={clicked?.point ?? null}
            onAnalyze={analyzePoint}
            onSave={saveLocation}
          />
          <SitePanel
            title={selectedSite?.name ?? null}
            description={selectedSite?.description ?? ''}
            sources={selectedSite?.sources ?? []}
            location={selectedLocation}
            settings={settings}
            onSettings={setSettings}
            viewOffsetHours={viewOffsetHours}
            onViewOffset={setViewOffsetHours}
            onMissionAnalysis={startAnalysis}
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
