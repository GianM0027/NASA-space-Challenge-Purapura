// ABOUTME: Comparison and trade-off view (UI-3, TO-1 to TO-4, TO-6): guided setup on the left, results on the right
// ABOUTME: Owner: Federico (D37). Self-contained: a pill in the App dock that opens a popup, like the AI assistant

import { useEffect, useMemo, useRef, useState } from 'react'
import { AiBadge } from '../ai/AiBadge'
import type { Site, TimeWindow, TradeoffResult } from '../api/contracts'
import { formatPercent, fromInputValue, toInputValue } from '../format'
import './compare.css'
import {
  activeFomIds,
  buildRequest,
  COMPUTED_FOMS,
  consistencyLabel,
  judgmentText,
  MAX_SCENARIOS,
  MAX_USER_FOMS,
  MIN_SCENARIOS,
  ordinal,
  pairKey,
  pairs,
  shortLabel,
  SLIDER_MAX,
  sliderToValue,
  type Mission,
  type TradeoffDraft,
  type UserFomDraft,
  valueToSlider,
  type WeightMode,
  validate,
} from './model'
import { downloadTradeoff, runTradeoff } from './tradeoffApi'
import { CloseButton } from '../ui/CloseButton'

type Props = {
  sites: Site[]
  /** Window of the site panel: its start seeds the scenarios, its length and step the mission. */
  defaultWindow: TimeWindow
  /** Site selected on the globe: it goes into scenario A when the popup opens, until a first run. */
  initialSiteId?: string | null
  /** Called with every new result (e.g. for a report); null never, the last result stays valid. */
  onResult?: (result: TradeoffResult) => void
}

const DURATIONS_H = [1, 7, 14, 30, 60].map((days) => days * 24)
const STEPS = [10, 30, 60, 240]
const LETTERS = 'ABCD'

const FOM_HINTS: Record<string, string> = {
  illumination_fraction: 'share of the window with the Sun above the terrain',
  longest_dark_h: 'longest continuous night',
  earth_visibility_fraction: 'share of the window with Earth above the terrain (direct link)',
  longest_earth_hidden_h: 'longest continuous loss of the direct link',
  landing_slope_max_deg: 'steepest ground in the landing ellipse',
  reachable_fraction: 'share of the operating range a rover can drive to',
}

const MODES: [WeightMode, string, string][] = [
  ['default', 'All equal', 'Every criterion counts the same.'],
  ['judgments', 'Compare in pairs', 'Move each slider towards the criterion that matters more (AHP, Saaty scale).'],
  ['direct', 'Set weights', 'Type a weight per criterion, on any scale: they are normalized to sum to 1.'],
]

function fomName(id: string, draft: TradeoffDraft, result: TradeoffResult | null): string {
  const fromResult = result?.foms.find((f) => f.id === id)
  if (fromResult) return fromResult.name
  const computed = COMPUTED_FOMS.find((f) => f.id === id)
  if (computed) return computed.name
  const k = Number(id.replace('user-', '')) - 1
  return draft.userFoms[k]?.name || `Custom criterion ${k + 1}`
}

function formatValue(value: number | null, unit: string): string {
  if (value === null) return 'n/a'
  if (unit === '') return formatPercent(value)
  return `${value.toFixed(value >= 100 ? 0 : 1)} ${unit}`
}

function missionSummary(m: Mission): string {
  const range = m.operatingRangeM > 0 ? `${m.operatingRangeM / 1000} km range` : 'no rover range'
  return `${m.durationHours / 24} days · every ${m.stepMinutes} min · ${m.landingPrecisionM} m landing · ${range}`
}

export function CompareView({ sites, defaultWindow, initialSiteId, onResult }: Props) {
  const hours = Math.round(
    (new Date(defaultWindow.end_utc).getTime() - new Date(defaultWindow.start_utc).getTime()) / 3_600_000,
  )
  /** The initial setup: scenario A on the selected site, B on another, default mission and weights. */
  const initialDraft = (): TradeoffDraft => {
    const first = sites.find((s) => s.id === initialSiteId) ?? sites[0]
    const second = sites.find((s) => s.id !== first?.id)
    const start = defaultWindow.start_utc
    return {
      scenarios: [
        { label: first ? shortLabel(first.name) : 'Scenario A', siteId: first?.id ?? '', startUtc: start },
        { label: second ? shortLabel(second.name) : 'Scenario B', siteId: second?.id ?? '', startUtc: start },
      ],
      mission: {
        durationHours: DURATIONS_H.includes(hours) ? hours : 30 * 24,
        stepMinutes: defaultWindow.step_minutes,
        landingPrecisionM: 100,
        operatingRangeM: 2000,
        traverseLimitDeg: 20,
        observerHeightM: 2,
      },
      excluded: [],
      userFoms: [],
      mode: 'default',
      judgments: {},
      weights: {},
    }
  }
  const [draft, setDraft] = useState<TradeoffDraft>(initialDraft)
  const [result, setResult] = useState<TradeoffResult | null>(null)
  const results = useRef<HTMLDivElement>(null)
  const [busy, setBusy] = useState<'run' | 'export' | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Closed = minimized to a pill: the component stays mounted, so the setup and the result survive.
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const errors = useMemo(() => validate(draft), [draft])
  const ids = useMemo(() => activeFomIds(draft), [draft])
  const siteName = (id: string) => shortLabel(sites.find((s) => s.id === id)?.name ?? id)

  const update = (change: Partial<TradeoffDraft>) => {
    setDraft((d) => ({ ...d, ...change }))
  }
  const setMission = (change: Partial<Mission>) => update({ mission: { ...draft.mission, ...change } })
  const setScenario = (k: number, change: Partial<TradeoffDraft['scenarios'][number]>) =>
    update({ scenarios: draft.scenarios.map((s, i) => (i === k ? { ...s, ...change } : s)) })
  const setUserFom = (k: number, change: Partial<UserFomDraft>) =>
    update({ userFoms: draft.userFoms.map((f, i) => (i === k ? { ...f, ...change } : f)) })

  const addScenario = () => {
    const used = new Set(draft.scenarios.map((s) => s.siteId))
    const next = sites.find((s) => !used.has(s.id))
    update({
      scenarios: [
        ...draft.scenarios,
        {
          label: next ? shortLabel(next.name) : `Scenario ${LETTERS[draft.scenarios.length]}`,
          siteId: next?.id ?? '',
          startUtc: defaultWindow.start_utc,
        },
      ],
      userFoms: draft.userFoms.map((f) => ({ ...f, values: [...f.values, ''] })),
    })
  }
  const removeScenario = (k: number) =>
    update({
      scenarios: draft.scenarios.filter((_, i) => i !== k),
      userFoms: draft.userFoms.map((f) => ({ ...f, values: f.values.filter((_, i) => i !== k) })),
    })
  const toggleFom = (id: string, on: boolean) =>
    update({ excluded: on ? draft.excluded.filter((x) => x !== id) : [...draft.excluded, id] })

  const call = async (kind: 'run' | 'export') => {
    setBusy(kind)
    setError(null)
    try {
      if (kind === 'run') {
        const next = await runTradeoff(buildRequest(draft))
        setResult(next)
        onResult?.(next)
        // Narrow screens stack the setup above the results: bring the results into view.
        if (globalThis.matchMedia?.('(max-width: 900px)').matches) {
          requestAnimationFrame(() => results.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
        }
      }
      else await downloadTradeoff(buildRequest(draft), 'lunarnav-tradeoff.xlsx')
    } catch (reason: unknown) {
      setError(String(reason instanceof Error ? reason.message : reason))
    } finally {
      setBusy(null)
    }
  }

  const resetAll = () => {
    setDraft(initialDraft())
    setResult(null)
    setError(null)
  }

  const openPopup = () => {
    if (!result) {
      // Before a first run: the sites may have arrived after mounting (App loads them async), so fill the
      // scenarios still without a site from a fresh setup, and let scenario A follow the globe selection.
      const fresh = initialDraft()
      const picked = sites.find((s) => s.id === initialSiteId)
      setDraft((d) => ({
        ...d,
        scenarios: d.scenarios.map((s, k) => {
          if (k === 0 && picked) return { ...s, siteId: picked.id, label: shortLabel(picked.name) }
          return s.siteId ? s : (fresh.scenarios[k] ?? s)
        }),
      }))
    }
    setOpen(true)
  }

  if (!open) {
    return (
      <button className="ai-pill cmp-pill" onClick={openPopup}>
        Trade-off{result ? ` · 1st ${result.labels[result.ranking[0]]}` : ''}
      </button>
    )
  }

  return (
    <div className="cmp-backdrop" onClick={(e) => e.target === e.currentTarget && setOpen(false)}>
    <div className="cmp-overlay" role="dialog" aria-modal="true" aria-label="Compare scenarios and trade-off">
      <header className="cmp-head">
        <div>
          <h2>Compare landing scenarios</h2>
          <p className="muted small">Pick 2 to 4 landing sites, choose what matters, and get a ranked trade-off.</p>
        </div>
        <div className="cmp-head-actions">
          <button onClick={resetAll} disabled={busy !== null} title="Back to the initial setup; clears the result">
            Reset
          </button>
          <CloseButton what="the comparison" hint="setup and result are kept · Esc" onClick={() => setOpen(false)} />
        </div>
      </header>

      <div className="cmp-layout">
        <div className="cmp-setup">
          <section className="cmp-step">
            <h3>
              <span className="cmp-num">1</span> Scenarios
              <span className="muted small">
                {draft.scenarios.length} of {MAX_SCENARIOS}
              </span>
            </h3>
            {draft.scenarios.map((s, k) => (
              <div className="cmp-scenario" key={k}>
                <div className="cmp-scenario-top">
                  <span className="cmp-letter">{LETTERS[k]}</span>
                  <select
                    className="cmp-site"
                    value={s.siteId}
                    title={sites.find((x) => x.id === s.siteId)?.name}
                    aria-label={`Scenario ${LETTERS[k]} landing site`}
                    onChange={(e) => setScenario(k, { siteId: e.target.value, label: siteName(e.target.value) })}
                  >
                    <option value="">Pick a landing site…</option>
                    {sites.map((site) => (
                      <option key={site.id} value={site.id}>
                        {site.name}
                      </option>
                    ))}
                  </select>
                  <button
                    className="cmp-icon"
                    onClick={() => removeScenario(k)}
                    disabled={draft.scenarios.length <= MIN_SCENARIOS}
                    title="Remove scenario"
                    aria-label={`Remove scenario ${LETTERS[k]}`}
                  >
                    ×
                  </button>
                </div>
                <div className="cmp-scenario-fields">
                  <label>
                    Name in the results
                    <input value={s.label} onChange={(e) => setScenario(k, { label: e.target.value })} />
                  </label>
                  <label>
                    Mission start (UTC)
                    <input
                      type="datetime-local"
                      value={toInputValue(s.startUtc)}
                      onChange={(e) => e.target.value && setScenario(k, { startUtc: fromInputValue(e.target.value) })}
                    />
                  </label>
                </div>
              </div>
            ))}
            {draft.scenarios.length < MAX_SCENARIOS && (
              <button className="cmp-add" onClick={addScenario}>
                + Add scenario
              </button>
            )}
          </section>

          <section className="cmp-step">
            <details>
              <summary>
                <h3>
                  <span className="cmp-num">2</span> Mission settings
                </h3>
                <span className="muted small">{missionSummary(draft.mission)} · edit</span>
              </summary>
              <p className="muted small">The same for every scenario, so the comparison is fair.</p>
              <div className="cmp-grid">
                <label>
                  Duration
                  <select value={draft.mission.durationHours} onChange={(e) => setMission({ durationHours: Number(e.target.value) })}>
                    {DURATIONS_H.map((h) => (
                      <option key={h} value={h}>
                        {h / 24} {h === 24 ? 'day' : 'days'}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Time step
                  <select value={draft.mission.stepMinutes} onChange={(e) => setMission({ stepMinutes: Number(e.target.value) })}>
                    {STEPS.map((m) => (
                      <option key={m} value={m}>
                        {m} min
                      </option>
                    ))}
                  </select>
                </label>
                <NumberField label="Landing precision (m)" value={draft.mission.landingPrecisionM} onChange={(v) => setMission({ landingPrecisionM: v })} />
                <NumberField label="Rover range (m, 0 = none)" value={draft.mission.operatingRangeM} onChange={(v) => setMission({ operatingRangeM: v })} />
                <NumberField label="Max rover slope (deg)" value={draft.mission.traverseLimitDeg} max={90} onChange={(v) => setMission({ traverseLimitDeg: v })} />
                <NumberField label="Solar panel height (m)" value={draft.mission.observerHeightM} onChange={(v) => setMission({ observerHeightM: v })} />
              </div>
            </details>
          </section>

          <section className="cmp-step">
            <h3>
              <span className="cmp-num">3</span> What matters
              <span className="muted small">{ids.length} criteria</span>
            </h3>
            <ul className="cmp-criteria">
              {COMPUTED_FOMS.map((f) => {
                const na = f.id === 'reachable_fraction' && draft.mission.operatingRangeM <= 0
                return (
                  <li key={f.id} className={na ? 'muted' : undefined}>
                    <label>
                      <input
                        type="checkbox"
                        disabled={na}
                        checked={!na && !draft.excluded.includes(f.id)}
                        onChange={(e) => toggleFom(f.id, e.target.checked)}
                      />
                      <span>
                        <strong>{f.name}</strong> <span className="cmp-dir">{f.direction === 'higher' ? '↑ more is better' : '↓ less is better'}</span>
                        <br />
                        <span className="muted small">{na ? 'needs a rover range in the mission settings' : FOM_HINTS[f.id]}</span>
                      </span>
                    </label>
                  </li>
                )
              })}
            </ul>

            {draft.userFoms.map((fom, k) => (
              <div className="cmp-custom" key={k}>
                <div className="cmp-custom-top">
                  <input
                    placeholder="Criterion name, e.g. Science interest"
                    value={fom.name}
                    aria-label={`Custom criterion ${k + 1} name`}
                    onChange={(e) => setUserFom(k, { name: e.target.value })}
                  />
                  <input
                    className="cmp-unit"
                    placeholder="Unit"
                    value={fom.unit}
                    aria-label={`Custom criterion ${k + 1} unit`}
                    onChange={(e) => setUserFom(k, { unit: e.target.value })}
                  />
                  <select
                    value={fom.direction}
                    aria-label={`Custom criterion ${k + 1} direction`}
                    onChange={(e) => setUserFom(k, { direction: e.target.value as 'higher' | 'lower' })}
                  >
                    <option value="higher">↑ more is better</option>
                    <option value="lower">↓ less is better</option>
                  </select>
                  <button
                    className="cmp-icon"
                    title="Remove criterion"
                    aria-label={`Remove custom criterion ${k + 1}`}
                    onClick={() => update({ userFoms: draft.userFoms.filter((_, i) => i !== k) })}
                  >
                    ×
                  </button>
                </div>
                <div className="cmp-custom-values">
                  {draft.scenarios.map((s, i) => (
                    <label key={i}>
                      <span title={s.label}>
                        {LETTERS[i]} · {s.label}
                      </span>
                      <input
                        inputMode="decimal"
                        placeholder="value"
                        value={fom.values[i] ?? ''}
                        onChange={(e) => setUserFom(k, { values: fom.values.map((v, x) => (x === i ? e.target.value : v)) })}
                      />
                    </label>
                  ))}
                </div>
              </div>
            ))}
            {draft.userFoms.length < MAX_USER_FOMS && (
              <button
                className="cmp-add"
                onClick={() =>
                  update({ userFoms: [...draft.userFoms, { name: '', unit: '', direction: 'higher', values: draft.scenarios.map(() => '') }] })
                }
              >
                + Add your own criterion (cost, science interest, …)
              </button>
            )}
          </section>

          <section className="cmp-step">
            <h3>
              <span className="cmp-num">4</span> How much each criterion counts
            </h3>
            <div className="cmp-segment" role="tablist">
              {MODES.map(([mode, label]) => (
                <button
                  key={mode}
                  role="tab"
                  aria-selected={draft.mode === mode}
                  className={draft.mode === mode ? 'active' : undefined}
                  onClick={() => update({ mode })}
                >
                  {label}
                </button>
              ))}
            </div>
            <p className="muted small">{MODES.find(([m]) => m === draft.mode)?.[2]}</p>

            {draft.mode === 'judgments' &&
              pairs(ids).map(([a, b]) => {
                const value = draft.judgments[pairKey(a, b)] ?? 1
                const nameA = fomName(a, draft, result)
                const nameB = fomName(b, draft, result)
                return (
                  <div className="cmp-pair" key={pairKey(a, b)}>
                    <div className="cmp-pair-names">
                      <span className={value > 1 ? 'cmp-win' : undefined}>{nameA}</span>
                      <span className={value < 1 ? 'cmp-win' : undefined}>{nameB}</span>
                    </div>
                    <input
                      type="range"
                      min={-SLIDER_MAX}
                      max={SLIDER_MAX}
                      step={1}
                      value={valueToSlider(value)}
                      aria-label={`${nameA} versus ${nameB}`}
                      onChange={(e) => update({ judgments: { ...draft.judgments, [pairKey(a, b)]: sliderToValue(Number(e.target.value)) } })}
                    />
                    <div className="cmp-pair-text small">{judgmentText(nameA, nameB, value)}</div>
                  </div>
                )
              })}

            {draft.mode === 'direct' && (
              <div className="cmp-weights">
                {ids.map((id) => (
                  <label key={id}>
                    <span>{fomName(id, draft, result)}</span>
                    <input
                      type="number"
                      min={0}
                      value={draft.weights[id] ?? 1}
                      onChange={(e) => {
                        const v = Number(e.target.value)
                        if (Number.isFinite(v) && v >= 0) update({ weights: { ...draft.weights, [id]: v } })
                      }}
                    />
                  </label>
                ))}
              </div>
            )}
          </section>
        </div>

        <div className="cmp-results" ref={results}>
          <div className="cmp-run">
            <button className="cmp-primary" disabled={errors.length > 0 || busy !== null} onClick={() => call('run')}>
              {busy === 'run' ? 'Computing… (can take a minute)' : result ? 'Run again' : 'Run trade-off'}
            </button>
            <button disabled={errors.length > 0 || busy !== null || !result} onClick={() => call('export')}>
              {busy === 'export' ? 'Preparing…' : 'Download Excel'}
            </button>
          </div>
          {errors.length > 0 && (
            <ul className="cmp-errors">
              {errors.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          )}
          {error && <p className="error small">{error}</p>}

          {result ? (
            <Results result={result} />
          ) : (
            <div className="cmp-empty">
              <p>
                <strong>No results yet.</strong>
              </p>
              <p className="muted small">
                Set up the scenarios on the left and press <em>Run trade-off</em>. Each landing site is simulated over the mission window,
                then scored on the criteria you kept. The Excel download contains the same trade-off with live formulas you can edit.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
    </div>
  )
}

function Results({ result }: { result: TradeoffResult }) {
  const cr = consistencyLabel(result.consistency_ratio)
  const best = Math.max(...result.scores)
  return (
    <>
      <section className="cmp-card">
        <h3>Ranking</h3>
        <ol className="cmp-ranking">
          {result.ranking.map((s, position) => (
            <li className={position === 0 ? 'best' : undefined} key={s}>
              <span className="cmp-place">{ordinal(position)}</span>
              <span className="cmp-rank-name" title={result.labels[s]}>
                {result.labels[s]}
              </span>
              <div className="cmp-bar">
                <div style={{ width: `${(100 * result.scores[s]) / best}%` }} />
              </div>
              <strong>{result.scores[s].toFixed(3)}</strong>
            </li>
          ))}
        </ol>
        <p className={`small ${cr.ok ? 'muted' : 'error'}`}>
          Score = weighted sum of the normalized criteria (sums to 1 over the scenarios). Consistency of the judgments: {cr.text}.
        </p>
        {result.ai_comment && (
          <p className="cmp-comment">
            <AiBadge />
            {result.ai_comment}
          </p>
        )}
      </section>

      <section className="cmp-card">
        <h3>Details per criterion</h3>
        <div className="cmp-table-wrap">
          <table className="cmp-table">
            <thead>
              <tr>
                <th>Criterion</th>
                <th>Weight</th>
                {result.labels.map((l) => (
                  <th key={l} title={l}>
                    {l}
                  </th>
                ))}
                <th title="Smallest weight change, in % of the weight, that swaps two scenarios">Robustness</th>
              </tr>
            </thead>
            <tbody>
              {result.foms.map((f) => {
                const sens = result.sensitivity.find((x) => x.fom_id === f.id)
                const column = result.table.map((row) => row[f.id]?.normalized ?? 0)
                const top = Math.max(...column)
                return (
                  <tr key={f.id}>
                    <td>
                      {f.name} <span className="muted">{f.direction === 'higher' ? '↑' : '↓'}</span>
                      {f.user_supplied && <span className="cmp-tag">yours</span>}
                    </td>
                    <td>{(100 * result.weights[f.id]).toFixed(0)} %</td>
                    {result.table.map((row, s) => (
                      <td key={s} className={row[f.id]?.normalized === top ? 'cmp-top' : undefined}>
                        {formatValue(row[f.id]?.value ?? null, f.unit)}
                      </td>
                    ))}
                    <td>{sens?.min_change_percent != null ? `±${sens.min_change_percent.toFixed(0)} %` : 'robust'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <p className="muted small">
          Green: best scenario on that criterion. Robustness: how much that weight must change (in % of itself) before two
          scenarios swap places; "robust" when even a 100 % change does not.
        </p>
        <details>
          <summary className="small">Method and sources</summary>
          <p className="small muted">{result.method}</p>
          <p className="small muted">Weights: {result.weight_method}</p>
        </details>
      </section>
    </>
  )
}

function NumberField(props: { label: string; value: number; max?: number; onChange: (value: number) => void }) {
  return (
    <label>
      {props.label}
      <input
        type="number"
        min={0}
        max={props.max}
        value={props.value}
        onChange={(e) => {
          const v = Number(e.target.value)
          if (Number.isFinite(v) && v >= 0) props.onChange(v)
        }}
      />
    </label>
  )
}
