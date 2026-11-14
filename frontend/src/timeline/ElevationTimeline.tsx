// ABOUTME: Elevation timeline (spec UI-2): Sun and Earth elevation against the terrain horizon
// ABOUTME: Owner: Gian. Plain SVG; draws exactly the per-sample horizon and visibility of the Evaluation

import { useState } from 'react'
import type { Evaluation } from '../api/contracts'
import { formatUtc } from '../format'
import { elevationRange, timeTicks, visibleBands } from './scale'

const WIDTH = 340
const CHART_HEIGHT = 92
const LEFT = 30
const RIGHT = 6
const TOP = 6
const GAP = 22
const AXIS = 18

type Body = {
  label: string
  color: string
  elevation: number[]
  horizon: number[]
  visible: boolean[]
}

/** SVG path through `values`, one point per sample. */
function path(values: number[], x: (i: number) => number, y: (v: number) => number): string {
  return values.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('')
}

/** Closed area between the horizon line and the bottom of the chart: the terrain. */
function terrain(values: number[], x: (i: number) => number, y: (v: number) => number, bottom: number) {
  const last = values.length - 1
  return `${path(values, x, y)}L${x(last).toFixed(1)},${bottom}L${x(0).toFixed(1)},${bottom}Z`
}

/** Sun and Earth elevation charts sharing one time axis and one hover cursor. */
export function ElevationTimeline({ evaluation }: { evaluation: Evaluation }) {
  const [cursor, setCursor] = useState<number | null>(null)
  const n = evaluation.times_utc.length
  if (n < 2) return null

  const bodies: Body[] = [
    {
      label: 'Sun',
      color: '#ffd166',
      elevation: evaluation.sun_elevation_deg,
      horizon: evaluation.sun_horizon_elevation_deg,
      visible: evaluation.sun_visible,
    },
    {
      label: 'Earth',
      color: '#4f8fff',
      elevation: evaluation.earth_elevation_deg,
      horizon: evaluation.earth_horizon_elevation_deg,
      visible: evaluation.earth_visible,
    },
  ]
  const plotWidth = WIDTH - LEFT - RIGHT
  const x = (i: number) => LEFT + (i / (n - 1)) * plotWidth
  const height = TOP + bodies.length * CHART_HEIGHT + (bodies.length - 1) * GAP + AXIS
  const window = evaluation.window
  const spanHours = (n - 1) * (window.step_minutes / 60)
  const ticks = timeTicks(window.start_utc, spanHours, window.step_minutes)

  const onMove = (event: React.PointerEvent<SVGSVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    const px = ((event.clientX - rect.left) / rect.width) * WIDTH
    const i = Math.round(((px - LEFT) / plotWidth) * (n - 1))
    setCursor(i >= 0 && i < n ? i : null)
  }

  return (
    <div className="timeline">
      <svg
        viewBox={`0 0 ${WIDTH} ${height}`}
        onPointerMove={onMove}
        onPointerLeave={() => setCursor(null)}
        role="img"
        aria-label="Sun and Earth elevation against the terrain horizon"
      >
        {bodies.map((body, k) => {
          const top = TOP + k * (CHART_HEIGHT + GAP)
          const bottom = top + CHART_HEIGHT
          const [low, high] = elevationRange(body.elevation, body.horizon)
          const y = (v: number) => bottom - ((v - low) / (high - low)) * CHART_HEIGHT
          const clip = `clip-${body.label}`
          return (
            <g key={body.label}>
              <defs>
                <clipPath id={clip}>
                  <rect x={LEFT} y={top} width={plotWidth} height={CHART_HEIGHT} />
                </clipPath>
              </defs>
              <text x={LEFT} y={top - 1} className="timeline-title" fill={body.color}>
                {body.label}
              </text>
              <g clipPath={`url(#${clip})`}>
                {visibleBands(body.visible).map(([a, b]) => (
                  <rect
                    key={a}
                    x={x(a)}
                    y={top}
                    width={Math.max(x(Math.min(b, n - 1)) - x(a), 1)}
                    height={CHART_HEIGHT}
                    fill={body.color}
                    opacity={0.12}
                  />
                ))}
                <path d={terrain(body.horizon, x, y, bottom)} fill="#5b5f6b" opacity={0.55} />
                <line x1={LEFT} x2={WIDTH - RIGHT} y1={y(0)} y2={y(0)} className="timeline-zero" />
                <path d={path(body.elevation, x, y)} fill="none" stroke={body.color} strokeWidth={1.4} />
              </g>
              <rect x={LEFT} y={top} width={plotWidth} height={CHART_HEIGHT} className="timeline-frame" />
              <text x={LEFT - 3} y={y(high) + 8} className="timeline-axis" textAnchor="end">
                {high}°
              </text>
              <text x={LEFT - 3} y={y(low)} className="timeline-axis" textAnchor="end">
                {low}°
              </text>
              {low < 0 && high > 0 && (
                <text x={LEFT - 3} y={y(0) + 3} className="timeline-axis" textAnchor="end">
                  0°
                </text>
              )}
            </g>
          )
        })}
        {ticks.map((tick) => (
          <text
            key={tick.index}
            x={x(tick.index)}
            y={height - 4}
            className="timeline-axis"
            textAnchor="middle"
          >
            {tick.label}
          </text>
        ))}
        {cursor !== null && (
          <line x1={x(cursor)} x2={x(cursor)} y1={TOP} y2={height - AXIS} className="timeline-cursor" />
        )}
      </svg>
      <p className="muted small timeline-readout">
        {cursor === null
          ? 'Shaded: body visible above the terrain. Grey: terrain horizon in the body direction.'
          : `${formatUtc(evaluation.times_utc[cursor])}: Sun ${evaluation.sun_elevation_deg[cursor].toFixed(1)}° ` +
            `(horizon ${evaluation.sun_horizon_elevation_deg[cursor].toFixed(1)}°, ` +
            `${evaluation.sun_visible[cursor] ? 'lit' : 'dark'}), Earth ` +
            `${evaluation.earth_elevation_deg[cursor].toFixed(1)}° ` +
            `(horizon ${evaluation.earth_horizon_elevation_deg[cursor].toFixed(1)}°, ` +
            `${evaluation.earth_visible[cursor] ? 'in view' : 'hidden'})`}
      </p>
    </div>
  )
}
