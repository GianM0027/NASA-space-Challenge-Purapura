// ABOUTME: Mission analysis window (spec UI-5, AI-6): one tab per analyzed site, minimizable
// ABOUTME: Owner: Gian. Shows the AI comment, Michael's summary, date-slip and dispersion tables

import { useState } from 'react'
import { tabLabels } from './tabLabels'
import { AiBadge } from '../ai/AiBadge'
import type { DispersionSample, GeoPoint, RobustnessReport, TimeWindow, VisibilityMetrics } from '../api/contracts'
import { formatDuration, formatPercent, formatShiftDays, formatUtc } from '../format'
import { bearingDeg, classify, compass, isSteep, SAME_FRACTION, SLOPE_LIMIT_DEG, touchdownVerdict } from './dispersion'
import { CloseButton } from '../ui/CloseButton'

/** One analysis tab: its request, then the report and the AI comment as they arrive. */
export type AnalysisTab = {
  id: string
  label: string
  window: TimeWindow
  landingPrecisionM: number
  /** The analyzed point: center of the touchdown diagram. */
  center: GeoPoint
  report: RobustnessReport | null
  /** True once the AI comment request has finished, with or without a comment. */
  commentDone: boolean
  error: string | null
}

/** Signed difference of two fractions in percentage points, e.g. "-12 pp". */
function deltaPoints(value: number, nominal: number): string {
  const points = Math.round((value - nominal) * 100)
  return points === 0 ? '±0' : `${points > 0 ? '+' : ''}${points} pp`
}

/** One row of the date-slip table. */
function ShiftRow(props: { label: string; metrics: VisibilityMetrics; nominal: VisibilityMetrics }) {
  const { label, metrics, nominal } = props
  const worse = metrics.illumination_fraction < nominal.illumination_fraction - 0.005
  return (
    <tr className={worse ? 'bad' : undefined}>
      <td>{label}</td>
      <td>
        {formatPercent(metrics.illumination_fraction)}
        {label !== 'nominal' && (
          <span className="muted"> {deltaPoints(metrics.illumination_fraction, nominal.illumination_fraction)}</span>
        )}
      </td>
      <td>{formatDuration(metrics.longest_dark_h)}</td>
      <td>{formatPercent(metrics.earth_visibility_fraction)}</td>
    </tr>
  )
}

/** The AI comment of a tab; nothing when the AI gave none that passed the number check. */
function AnalysisText({ report, done }: { report: RobustnessReport; done: boolean }) {
  if (report.ai_comment) {
    return (
      <p className="analysis-comment">
        <AiBadge />
        {report.ai_comment}
      </p>
    )
  }
  return done ? null : <p className="muted small">AI comment on the way…</p>
}

const DIAGRAM = 150
const RING_PX = 58

const CLASS_LABEL: Record<string, string> = {
  same: `as at the target (within ${SAME_FRACTION * 100} point)`,
  better: 'more Sun or Earth',
  worse: 'less Sun or Earth',
}
const STEEP_LABEL = `red ring: landing slope over ${SLOPE_LIMIT_DEG}°`

/** Target diagram: the analyzed point in the middle, each touchdown sample where it lies. */
/** One touchdown point in words: offset, bearing, Sun, Earth, slope and how it compares. */
function dotText(sample: DispersionSample, nominal: VisibilityMetrics, center: GeoPoint): string {
  const kind = classify(sample, nominal)
  const steep = isSteep(sample)
  return (
    `${Math.round(sample.offset_m)} m ${compass(bearingDeg(center, sample.location))}: Sun ${formatPercent(sample.metrics.illumination_fraction)}, ` +
    `Earth ${formatPercent(sample.metrics.earth_visibility_fraction)}, landing slope ${sample.slope_max_deg.toFixed(1)}° (${CLASS_LABEL[kind]}${steep ? `, slope over ${SLOPE_LIMIT_DEG}°` : ''})`
  )
}

function TouchdownDiagram(props: {
  samples: DispersionSample[]
  nominal: VisibilityMetrics
  center: GeoPoint
  picked: number | null
  onPick: (index: number) => void
}) {
  const { samples, nominal, center, picked, onPick } = props
  const radius = Math.max(...samples.map((sample) => sample.offset_m))
  const mid = DIAGRAM / 2
  const rings = [...new Set(samples.map((sample) => Math.round(sample.offset_m)))].sort((a, b) => a - b)
  return (
    <svg className="touchdown" viewBox={`0 0 ${DIAGRAM} ${DIAGRAM}`} role="img" aria-label="Touchdown points around the target">
      {rings.map((ring) => (
        <g key={ring}>
          <circle cx={mid} cy={mid} r={(ring / radius) * RING_PX} className="touchdown-ring" />
          {/* On the north-east diagonal, so the label never sits on the N or E letters. */}
          <text
            x={mid + ((ring / radius) * RING_PX) * Math.SQRT1_2 + 3}
            y={mid - ((ring / radius) * RING_PX) * Math.SQRT1_2 - 3}
            className="touchdown-label"
          >
            {ring} m
          </text>
        </g>
      ))}
      {(['N', 'E', 'S', 'W'] as const).map((label, k) => {
        const angle = (k * Math.PI) / 2
        return (
          <text
            key={label}
            x={mid + Math.sin(angle) * (RING_PX + 10)}
            y={mid - Math.cos(angle) * (RING_PX + 10) + 3}
            className="touchdown-label"
            textAnchor="middle"
          >
            {label}
          </text>
        )
      })}
      <circle cx={mid} cy={mid} r={4} className="touchdown-target" />
      {samples.map((sample, i) => {
        const bearing = (bearingDeg(center, sample.location) * Math.PI) / 180
        const r = (sample.offset_m / radius) * RING_PX
        const kind = classify(sample, nominal)
        const steep = isSteep(sample)
        return (
          <circle
            key={i}
            cx={mid + Math.sin(bearing) * r}
            cy={mid - Math.cos(bearing) * r}
            r={5}
            className={`touchdown-dot ${kind}${steep ? ' steep' : ''}${picked === i ? ' picked' : ''}`}
            onClick={() => onPick(i)}
          >
            <title>{dotText(sample, nominal, center)}</title>
          </circle>
        )
      })}
    </svg>
  )
}

/** "Where the lander touches down": verdict sentence, target diagram, numbers on demand. */
function TouchdownView({ report, center }: { report: RobustnessReport; center: GeoPoint }) {
  const samples = report.dispersion
  // Tapped dot (touch screens have no hover): its numbers show under the diagram.
  const [picked, setPicked] = useState<number | null>(null)
  const kinds = new Set(samples.map((sample) => classify(sample, report.nominal)))
  const anySteep = samples.some(isSteep)
  return (
    <>
      <p className="small">{touchdownVerdict(samples, report.nominal, center)}</p>
      {samples.length > 0 && (
        <>
          <div className="touchdown-row">
            <TouchdownDiagram
              samples={samples}
              nominal={report.nominal}
              center={center}
              picked={picked}
              onPick={(i) => setPicked(picked === i ? null : i)}
            />
            <ul className="touchdown-legend small">
              <li>
                <i className="touchdown-target" /> target point
              </li>
              {(['same', 'better', 'worse'] as const)
                .filter((kind) => kinds.has(kind))
                .map((kind) => (
                  <li key={kind}>
                    <i className={`touchdown-dot ${kind}`} /> {CLASS_LABEL[kind]}
                  </li>
                ))}
              {anySteep && (
                <li>
                  <i className="touchdown-dot steep" /> {STEEP_LABEL}
                </li>
              )}
              <li className="muted">Tap or hover a dot for its numbers.</li>
            </ul>
          </div>
          {picked !== null && samples[picked] && (
            <p className="small touchdown-picked">{dotText(samples[picked], report.nominal, center)}</p>
          )}
          <details>
            <summary className="muted small">Details</summary>
            <table className="analysis-table">
              <thead>
                <tr>
                  <th>point</th>
                  <th>Sun</th>
                  <th>Earth</th>
                  <th>landing slope</th>
                </tr>
              </thead>
              <tbody>
                {samples.map((sample, i) => (
                  <tr key={i}>
                    <td>
                      {Math.round(sample.offset_m)} m {compass(bearingDeg(center, sample.location))}
                    </td>
                    <td>{formatPercent(sample.metrics.illumination_fraction)}</td>
                    <td>{formatPercent(sample.metrics.earth_visibility_fraction)}</td>
                    <td>{sample.slope_max_deg.toFixed(1)}°</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        </>
      )}
    </>
  )
}

/** The content of one tab. */
function AnalysisView({ tab }: { tab: AnalysisTab }) {
  const { report } = tab
  const window = `${formatUtc(tab.window.start_utc)} → ${formatUtc(tab.window.end_utc)}`
  return (
    <div className="analysis-view">
      <h3 className="analysis-title">{tab.label}</h3>
      <p className="muted small">
        {window} · landing within {tab.landingPrecisionM} m
      </p>
      {tab.error && <p className="error small">{tab.error}</p>}
      {!report && !tab.error && <p className="muted small">Analyzing date slips and landing dispersion…</p>}
      {report && (
        <>
          <AnalysisText report={report} done={tab.commentDone} />

          <h3>If the launch slips</h3>
          <table className="analysis-table">
            <thead>
              <tr>
                <th>shift</th>
                <th>Sun</th>
                <th>longest dark</th>
                <th>Earth</th>
              </tr>
            </thead>
            <tbody>
              <ShiftRow label="nominal" metrics={report.nominal} nominal={report.nominal} />
              {report.date_shifts.map((shift) => (
                <ShiftRow
                  key={shift.shift_days}
                  label={formatShiftDays(shift.shift_days)}
                  metrics={shift.metrics}
                  nominal={report.nominal}
                />
              ))}
            </tbody>
          </table>

          <h3>Where the lander touches down</h3>
          <TouchdownView report={report} center={tab.center} />
        </>
      )}
    </div>
  )
}

/**
 * Floating window next to the AI box: one tab per analysis until the user closes it or resets.
 * Hidden while there is no analysis; minimized it is a pill like the AI one.
 */
export function MissionAnalysisBox(props: {
  tabs: AnalysisTab[]
  activeId: string | null
  minimized: boolean
  onSelect: (id: string) => void
  onClose: (id: string) => void
  onReset: () => void
  onMinimize: (minimized: boolean) => void
}) {
  const { tabs, activeId, minimized, onSelect, onClose, onReset, onMinimize } = props
  if (tabs.length === 0) return null
  if (minimized) {
    return (
      <button className="ai-pill analysis-pill" onClick={() => onMinimize(false)}>
        Mission analysis · {tabs.length}
      </button>
    )
  }
  const active = tabs.find((tab) => tab.id === activeId) ?? tabs[0]
  const labels = tabLabels(tabs)
  return (
    <section className="ai-box analysis-box" aria-label="Mission analysis">
      <div className="ai-head">
        <div className="tabs analysis-tabs" role="tablist">
          {tabs.map((tab, i) => (
            <span key={tab.id} className={tab.id === active.id ? 'analysis-tab active' : 'analysis-tab'}>
              <button role="tab" aria-selected={tab.id === active.id} onClick={() => onSelect(tab.id)} title={tab.label}>
                {labels[i]}
              </button>
              <button className="chip-remove" title="Close this analysis" onClick={() => onClose(tab.id)}>
                ×
              </button>
            </span>
          ))}
        </div>
        <button title="Close every analysis" onClick={onReset}>
          Reset
        </button>
        <CloseButton what="mission analysis" hint="the analyses are kept" onClick={() => onMinimize(true)} />
      </div>
      <AnalysisView tab={active} />
    </section>
  )
}
