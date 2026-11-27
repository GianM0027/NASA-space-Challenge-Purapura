// ABOUTME: Time wheel (spec UI-11): a jog-dial ruler that moves the shown instant inside the window
// ABOUTME: Owner: Gian. Mouse wheel or drag steps the time; play advances it at a chosen speed

import { useEffect, useRef, useState } from 'react'
import { formatUtc } from '../format'
import { formatOffset, moveOffset } from './wheel'

const WIDTH = 300
const HEIGHT = 34
const TICK_PX = 8
const TICKS = Math.ceil(WIDTH / TICK_PX / 2) + 1
// Play speeds, hours of Moon time per second of screen time.
const SPEEDS = [1, 6, 24]
const PLAY_TICK_MS = 250

/**
 * Jog-dial ruler: ticks slide under a fixed needle as the time moves.
 *
 * The offset is hours from the window start, snapped to the sampling step and kept inside the
 * window; every change goes to `onChange`, which updates the globe and the timeline cursor.
 */
export function TimeWheel(props: {
  startUtc: string
  windowHours: number
  stepMinutes: number
  offsetHours: number
  onChange: (offsetHours: number) => void
}) {
  const { startUtc, windowHours, stepMinutes, offsetHours, onChange } = props
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(SPEEDS[1])
  const drag = useRef<{ x: number; offset: number } | null>(null)
  const latest = useRef(offsetHours)
  useEffect(() => {
    latest.current = offsetHours
  }, [offsetHours])
  const stepH = stepMinutes / 60

  // Play: advance by speed hours per second; stop at the end of the window.
  useEffect(() => {
    if (!playing) return
    const timer = setInterval(() => {
      const steps = Math.max(1, Math.round((speed * PLAY_TICK_MS) / 1000 / stepH))
      const next = moveOffset(latest.current, steps, stepMinutes, windowHours)
      latest.current = next
      onChange(next)
      if (next >= windowHours) setPlaying(false)
    }, PLAY_TICK_MS)
    return () => clearInterval(timer)
  }, [playing, speed, stepH, stepMinutes, windowHours, onChange])

  // Native listener: React's wheel listener is passive, so it could not stop the panel scrolling.
  const dial = useRef<SVGSVGElement>(null)
  useEffect(() => {
    const element = dial.current
    if (!element) return
    const listener = (event: WheelEvent) => {
      event.preventDefault()
      const steps = (event.deltaY > 0 || event.deltaX > 0 ? 1 : -1) * (event.shiftKey ? 10 : 1)
      const next = moveOffset(latest.current, steps, stepMinutes, windowHours)
      latest.current = next
      onChange(next)
    }
    element.addEventListener('wheel', listener, { passive: false })
    return () => element.removeEventListener('wheel', listener)
  }, [stepMinutes, windowHours, onChange])

  const onPointerDown = (event: React.PointerEvent<SVGSVGElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId)
    drag.current = { x: event.clientX, offset: offsetHours }
    setPlaying(false)
  }
  const onPointerMove = (event: React.PointerEvent<SVGSVGElement>) => {
    if (!drag.current) return
    // Dragging the ruler left moves time forward, like turning a dial.
    const steps = Math.round((drag.current.x - event.clientX) / TICK_PX)
    onChange(moveOffset(drag.current.offset, steps, stepMinutes, windowHours))
  }

  const position = offsetHours / stepH
  const first = Math.floor(position) - TICKS
  const ticks = Array.from({ length: TICKS * 2 + 1 }, (_, k) => first + k)
  const shown = new Date(new Date(startUtc).getTime() + offsetHours * 3_600_000).toISOString()
  const stepsPerDay = Math.round(24 / stepH)

  return (
    <div className="time-wheel" title="Scroll or drag to move time; Shift + scroll for bigger steps">
      <div className="time-wheel-head">
        <span className="time-wheel-icon" aria-hidden>
          ⏱
        </span>
        {/* Date with the offset from the start under it, so the controls keep one line. */}
        <span className="time-wheel-when">
          <span className="time-wheel-now">{formatUtc(shown)}</span>
          <span className="muted small">{formatOffset(offsetHours)}</span>
        </span>
        <span className="grow" />
        <button
          title={playing ? 'Pause' : 'Play: move time forward automatically'}
          onClick={() => setPlaying(!playing)}
          disabled={!playing && offsetHours >= windowHours}
        >
          {playing ? '⏸' : '▶'}
        </button>
        <select value={speed} title="Play speed" onChange={(event) => setSpeed(Number(event.target.value))}>
          {SPEEDS.map((hours) => (
            <option key={hours} value={hours}>
              {hours} h/s
            </option>
          ))}
        </select>
        <button title="Back to the window start" onClick={() => onChange(0)} disabled={offsetHours === 0}>
          ⟲
        </button>
      </div>
      <svg
        ref={dial}
        className="time-wheel-dial"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={() => (drag.current = null)}
        role="slider"
        aria-label="Shown time"
        aria-valuemin={0}
        aria-valuemax={windowHours}
        aria-valuenow={offsetHours}
        aria-valuetext={formatUtc(shown)}
      >
        <defs>
          <linearGradient id="wheel-fade" x1="0" x2="1">
            <stop offset="0" stopColor="var(--surface)" stopOpacity="1" />
            <stop offset="0.2" stopColor="var(--surface)" stopOpacity="0" />
            <stop offset="0.8" stopColor="var(--surface)" stopOpacity="0" />
            <stop offset="1" stopColor="var(--surface)" stopOpacity="1" />
          </linearGradient>
        </defs>
        <rect x="0" y="4" width={WIDTH} height={HEIGHT - 8} rx="6" className="time-wheel-body" />
        {ticks.map((index) => {
          const x = WIDTH / 2 + (index - position) * TICK_PX
          const outside = index < 0 || index * stepH > windowHours
          const major = index % stepsPerDay === 0
          return (
            <line
              key={index}
              x1={x}
              x2={x}
              y1={major ? 8 : 13}
              y2={major ? HEIGHT - 8 : HEIGHT - 13}
              className={outside ? 'time-wheel-tick outside' : major ? 'time-wheel-tick major' : 'time-wheel-tick'}
            />
          )
        })}
        <rect x="0" y="4" width={WIDTH} height={HEIGHT - 8} rx="6" fill="url(#wheel-fade)" />
        <path d={`M${WIDTH / 2 - 5},2 L${WIDTH / 2 + 5},2 L${WIDTH / 2},8 Z`} className="time-wheel-needle" />
        <line x1={WIDTH / 2} x2={WIDTH / 2} y1={6} y2={HEIGHT - 4} className="time-wheel-needle-line" />
      </svg>
    </div>
  )
}
