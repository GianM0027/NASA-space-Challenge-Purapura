// ABOUTME: Admin usage dashboard (decision D47): visits per day, features used, top sites, devices, errors
// ABOUTME: Owner: Gian. Aggregate counts only (no cookies, no IDs); plain SVG charts in the app's palette

import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { api, type UsageStats } from '../api/client'
import type { Site } from '../api/contracts'
import { CloseButton } from '../ui/CloseButton'
import { accountError } from './errors'

const RANGES = [7, 30, 90] as const
const CHART_W = 640
const CHART_H = 140
const AXIS_H = 0

function shortDate(iso: string): string {
  const [, month, day] = iso.split('-')
  return `${Number(day)}/${Number(month)}`
}

/** Daily visits as bars; hovering or tapping a bar shows that day's visits and visitors. */
function VisitsChart({ stats }: { stats: UsageStats }) {
  const [picked, setPicked] = useState<number | null>(null)
  const n = stats.days.length
  const max = Math.max(1, ...stats.visits)
  const slot = CHART_W / n
  const gap = n > 45 ? 1 : 2
  const plotH = CHART_H - AXIS_H
  const shown = picked ?? n - 1
  return (
    <figure className="stats-figure">
      <figcaption className="stats-readout">
        <strong>{shortDate(stats.days[shown])}</strong>: {stats.visits[shown]} visit{stats.visits[shown] === 1 ? '' : 's'},{' '}
        {stats.visitors[shown]} visitor{stats.visitors[shown] === 1 ? '' : 's'}
        {picked === null && <span className="muted"> (today · hover or tap a bar)</span>}
      </figcaption>
      <div className="stats-plot">
      <span className="stats-axis stats-max">{max}</span>
      <svg
        className="stats-chart"
        viewBox={`0 0 ${CHART_W} ${CHART_H}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={`Visits per day over the last ${n} days, at most ${max} in a day`}
        onPointerLeave={() => setPicked(null)}
      >
        {[0.5, 1].map((f) => (
          <line key={f} x1={0} x2={CHART_W} y1={plotH - f * plotH} y2={plotH - f * plotH} className="stats-grid" />
        ))}
        {stats.visits.map((value, i) => {
          const h = (value / max) * plotH
          const x = i * slot + gap / 2
          const w = Math.max(1, slot - gap)
          return (
            <g key={stats.days[i]} onPointerEnter={() => setPicked(i)} onClick={() => setPicked(i)}>
              {/* Hit target: the whole column, taller than the bar. */}
              <rect x={i * slot} y={0} width={slot} height={plotH} className="stats-hit" />
              {value > 0 && (
                <path
                  d={roundedTop(x, plotH, w, h, Math.min(4, w / 2, h))}
                  className={i === shown ? 'stats-bar active' : 'stats-bar'}
                />
              )}
            </g>
          )
        })}
        <line x1={0} x2={CHART_W} y1={plotH} y2={plotH} className="stats-baseline" />
      </svg>
      </div>
      <div className="stats-dates stats-axis">
        <span>{shortDate(stats.days[0])}</span>
        <span>{shortDate(stats.days[Math.floor((n - 1) / 2)])}</span>
        <span>{shortDate(stats.days[n - 1])}</span>
      </div>
    </figure>
  )
}

/** A bar rising from the baseline at y0 with only its top corners rounded. */
function roundedTop(x: number, y0: number, w: number, h: number, r: number): string {
  const top = y0 - h
  return `M${x},${y0} V${top + r} Q${x},${top} ${x + r},${top} H${x + w - r} Q${x + w},${top} ${x + w},${top + r} V${y0} Z`
}

/** Horizontal bars with the name on the left and the count on the right. */
function BarList({ items, label }: { items: { name: string; count: number }[]; label: (name: string) => string }) {
  if (items.length === 0) return <p className="muted small">Nothing yet.</p>
  const max = Math.max(...items.map((item) => item.count))
  return (
    <ul className="stats-bars">
      {items.map((item) => (
        <li key={item.name}>
          <span className="stats-bar-name">{label(item.name)}</span>
          <span className="stats-bar-track" aria-hidden="true">
            <i style={{ width: `${(item.count / max) * 100}%` }} />
          </span>
          <span className="stats-bar-value">{item.count}</span>
        </li>
      ))}
    </ul>
  )
}

function Tile({ value, label }: { value: number | string; label: string }) {
  return (
    <div className="metric">
      <span className="metric-value">{value}</span>
      <span className="metric-label">{label}</span>
    </div>
  )
}

/** Full-screen dashboard; `sites` turns site ids into names. */
export function StatsDashboard(props: { sites: Site[]; onClose: () => void }) {
  const { sites, onClose } = props
  const [days, setDays] = useState<(typeof RANGES)[number]>(30)
  const [stats, setStats] = useState<UsageStats | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .adminStats(days)
      .then((next) => {
        setStats(next)
        setError(null)
      })
      .catch((reason: unknown) => setError(accountError(reason)))
  }, [days])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const names = new Map(sites.map((site) => [site.id, site.name]))
  const feature = (name: string) => stats?.features.find((f) => f.name === name)?.count ?? 0
  const visits = stats ? stats.visits.reduce((a, b) => a + b, 0) : 0
  const visitors = stats ? stats.visitors.reduce((a, b) => a + b, 0) : 0

  // Rendered on <body>: above the globe, the account popover and the phone tab bar.
  return createPortal(
    <div
      className="rpt-backdrop stats-backdrop"
      onPointerDown={(event) => event.stopPropagation()}
      onClick={(event) => event.target === event.currentTarget && onClose()}
    >
      <div className="rpt-dialog stats-dialog" role="dialog" aria-modal="true" aria-label="Usage statistics">
        <header className="rpt-head">
          <div>
            <h2>Usage statistics</h2>
            <p className="muted small">Counts only: no cookies, no IP addresses, nothing that identifies a visitor.</p>
          </div>
          <div className="tabs stats-range" role="group" aria-label="Period">
            {RANGES.map((range) => (
              <button key={range} className={range === days ? 'active' : undefined} onClick={() => setDays(range)}>
                {range} d
              </button>
            ))}
          </div>
          <CloseButton what="the statistics" hint="Esc" onClick={onClose} />
        </header>
        <div className="stats-body">
          {error && <p className="error small">{error}</p>}
          {!stats && !error && <p className="muted small">Loading…</p>}
          {stats && (
            <>
              <div className="metrics stats-tiles">
                <Tile value={visits} label={`visits in ${days} days`} />
                <Tile value={visitors} label="visitors (each counted once a day)" />
                <Tile
                  value={feature('site evaluation') + feature('mission analysis') + feature('trade-off')}
                  label="analyses run"
                />
                <Tile value={feature('AI question')} label="AI questions" />
              </div>
              <section>
                <h3>Visits per day</h3>
                <VisitsChart stats={stats} />
              </section>
              <div className="stats-columns">
                <section>
                  <h3>Features used</h3>
                  <BarList items={stats.features} label={(name) => name} />
                </section>
                <section>
                  <h3>Most analyzed sites</h3>
                  <BarList items={stats.sites} label={(id) => names.get(id) ?? id} />
                </section>
              </div>
              <div className="stats-columns">
                <section>
                  <h3>Devices</h3>
                  <BarList items={stats.devices} label={(name) => (name === 'phone' ? 'Phone or tablet' : 'Desktop')} />
                </section>
                <section>
                  <h3>Problems</h3>
                  {stats.errors.length === 0 ? (
                    <p className="small stats-ok">✓ No server errors or rate limits in this period.</p>
                  ) : (
                    <BarList
                      items={stats.errors}
                      label={(name) => (name === 'server error' ? '⚠ Server errors' : 'Requests over the rate limit')}
                    />
                  )}
                </section>
              </div>
              <p className="muted small">
                A visitor is counted once a day through a hash that changes every day and is never stored, so the
                same person on two days counts twice. A visit is one page load.
              </p>
            </>
          )}
        </div>
      </div>
    </div>,
    document.body,
  )
}
