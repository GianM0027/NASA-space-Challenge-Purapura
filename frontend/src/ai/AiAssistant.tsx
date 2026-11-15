// ABOUTME: AI box (spec UI-4): chat and ranking tabs sharing one bar of editable mission criteria
// ABOUTME: Owner: Gian. Edits rerank without the LLM; rationales arrive after the ranking

import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { ChatMessage, MissionRequirements, Site, SiteRanking, SiteScore, TimeWindow } from '../api/contracts'
import { formatUtc, hoursBetween } from '../format'
import {
  constraintsCount,
  fieldSpec,
  fieldValue,
  formatFieldValue,
  fromEditable,
  shownFields,
  toEditable,
  withField,
  type FieldSpec,
} from './criteria'

type Tab = 'chat' | 'ranking'

const SOURCE_LABEL: Record<string, string> = { user: 'you', archetype: 'archetype', region: 'region', default: 'GUI' }

/** One editable criterion chip: click to edit, × to remove. */
function Chip(props: {
  spec: FieldSpec
  requirements: MissionRequirements
  onChange: (field: string, value: number | null) => void
}) {
  const { spec, requirements, onChange } = props
  const value = fieldValue(requirements, spec.field)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  if (value === null) return null
  const source = requirements.field_sources[spec.field] ?? 'user'
  const commit = () => {
    const typed = Number(draft)
    setEditing(false)
    if (draft.trim() !== '' && Number.isFinite(typed)) onChange(spec.field, fromEditable(spec.unit, typed))
  }
  return (
    <span className={`chip ${source}`} title={requirements.rationale[spec.field] ?? ''}>
      {editing ? (
        <input
          autoFocus
          className="chip-input"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key === 'Enter') commit()
            if (event.key === 'Escape') setEditing(false)
          }}
        />
      ) : (
        <button
          className="chip-value"
          onClick={() => {
            setDraft(String(toEditable(spec.unit, value)))
            setEditing(true)
          }}
        >
          {spec.label} {spec.op === '=' ? '' : `${spec.op} `}
          {formatFieldValue(spec.unit, value)}
        </button>
      )}
      <span className="chip-source">{SOURCE_LABEL[source] ?? source}</span>
      <button className="chip-remove" title="Remove this constraint" onClick={() => onChange(spec.field, null)}>
        ×
      </button>
    </span>
  )
}

/** One ranked site: summary row, and when open the AI rationale and the per-criterion check. */
function RankRow(props: {
  score: SiteScore
  name: string
  requirements: MissionRequirements
  open: boolean
  onClick: () => void
}) {
  const { score, name, requirements, open, onClick } = props
  const [met, total] = constraintsCount(score)
  return (
    <li className={open ? 'rank-row open' : 'rank-row'}>
      <button className="rank-head" onClick={onClick}>
        <span className="rank-number">{score.rank}</span>
        <span className="rank-name">{name}</span>
        {score.all_constraints_met ? (
          <span className="score-bar" title={`score ${score.score.toFixed(2)}`}>
            <i style={{ width: `${Math.round(score.score * 100)}%` }} />
          </span>
        ) : (
          <span className="misses">
            misses {total - met} of {total}
          </span>
        )}
      </button>
      {open && (
        <div className="rank-detail">
          <p className="rationale">{score.rationale ?? 'Explanation on the way…'}</p>
          <table className="checks">
            <tbody>
              {Object.entries(score.constraints_met).map(([field, ok]) => {
                const spec = fieldSpec(field)
                const threshold = fieldValue(requirements, field)
                const value = score.criterion_values[field]
                if (!spec || threshold === null) return null
                return (
                  <tr key={field} className={ok ? 'ok' : 'bad'}>
                    <td>{ok ? '✓' : '✗'}</td>
                    <td>{spec.label}</td>
                    <td>{value === undefined ? 'n/a' : formatFieldValue(spec.unit, value)}</td>
                    <td className="muted">
                      {spec.op} {formatFieldValue(spec.unit, threshold)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </li>
  )
}

/**
 * Floating AI box over the globe. The conversation keeps its context until reset; every answer
 * updates the criteria bar, and a ranking fills the Ranking tab. Clicking a ranked site selects
 * it on the globe and in the site panel.
 */
export function AiAssistant(props: {
  sites: Site[]
  defaultWindow: TimeWindow
  /** Select a ranked site; the window is the mission window the ranking used. */
  onPickSite: (siteId: string, window: TimeWindow | null) => void
  /** Every new ranking, explanations included, e.g. for the PDF report (decision D42). */
  onRanking?: (ranking: SiteRanking) => void
}) {
  const { sites, defaultWindow, onPickSite, onRanking } = props
  // Starts as a pill: the box opens only when the user asks for it.
  const [minimized, setMinimized] = useState(true)
  const [tab, setTab] = useState<Tab>('chat')
  const [history, setHistory] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [requirements, setRequirements] = useState<MissionRequirements | null>(null)
  const [locked, setLocked] = useState<string[]>([])
  const [ranking, setRanking] = useState<SiteRanking | null>(null)
  const [unseen, setUnseen] = useState(false)
  const [open, setOpen] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showMisses, setShowMisses] = useState(false)
  // Increments on every new ranking, so a late explanation of an older ranking is dropped.
  const generation = useRef(0)
  const lastText = useRef('')

  const names = new Map(sites.map((site) => [site.id, site.name]))

  useEffect(() => {
    if (ranking) onRanking?.(ranking)
  }, [ranking, onRanking])

  const showRanking = (next: SiteRanking, firstTime: boolean) => {
    const mine = ++generation.current
    setRanking(next)
    setOpen(null)
    setShowMisses(!next.results.some((score) => score.all_constraints_met))
    if (firstTime) setTab('ranking')
    else setUnseen(true)
    api
      .explain({ ranking: next, language_hint: lastText.current })
      .then((explained) => mine === generation.current && setRanking(explained))
      .catch(() => undefined)
  }

  const send = async () => {
    const text = draft.trim()
    if (!text || busy) return
    setDraft('')
    setError(null)
    setBusy('Reading your request…')
    lastText.current = text
    const turn: ChatMessage = { role: 'user', text }
    setHistory((past) => [...past, turn])
    try {
      const answer = await api.ask({
        text,
        history,
        requirements,
        locked_fields: locked,
        default_window: defaultWindow,
      })
      setHistory((past) => [...past, { role: 'assistant', text: answer.message }])
      setRequirements(answer.requirements)
      if (answer.ranking) showRanking(answer.ranking, ranking === null)
    } catch (reason) {
      setError(String(reason))
    } finally {
      setBusy(null)
    }
  }

  const edit = async (field: string, value: number | null) => {
    if (!requirements) return
    const next = withField(requirements, field, value)
    setRequirements(next)
    setLocked((fields) => (fields.includes(field) ? fields : [...fields, field]))
    setError(null)
    setBusy('Ranking…')
    try {
      showRanking(await api.rank(next), ranking === null)
    } catch (reason) {
      setError(String(reason))
    } finally {
      setBusy(null)
    }
  }

  const reset = () => {
    generation.current++
    setHistory([])
    setRequirements(null)
    setLocked([])
    setRanking(null)
    setOpen(null)
    setError(null)
    setTab('chat')
  }

  if (minimized) {
    return (
      <button className="ai-pill" onClick={() => setMinimized(false)}>
        AI assistant{ranking ? ` · ${ranking.results.length} sites` : ''}
      </button>
    )
  }

  const chips = requirements ? shownFields(requirements) : []
  const window = requirements?.window
  const passing = ranking?.results.filter((score) => score.all_constraints_met) ?? []
  const missing = ranking?.results.filter((score) => !score.all_constraints_met) ?? []
  const row = (score: SiteScore) => (
    <RankRow
      key={score.site_id}
      score={score}
      name={names.get(score.site_id) ?? score.site_id}
      requirements={ranking!.requirements}
      open={open === score.site_id}
      onClick={() => {
        setOpen(open === score.site_id ? null : score.site_id)
        onPickSite(score.site_id, ranking!.requirements.window)
      }}
    />
  )

  return (
    <section className="ai-box" aria-label="AI assistant">
      <div className="ai-head">
        <div className="tabs">
          <button className={tab === 'chat' ? 'active' : undefined} onClick={() => setTab('chat')}>
            Chat
          </button>
          <button
            className={tab === 'ranking' ? 'active' : undefined}
            onClick={() => {
              setTab('ranking')
              setUnseen(false)
            }}
          >
            Ranking{ranking ? ` (${ranking.results.length})` : ''}
            {unseen && tab !== 'ranking' && <i className="unseen" />}
          </button>
        </div>
        <button title="Start a new conversation" onClick={reset}>
          Reset
        </button>
        <button title="Minimize" onClick={() => setMinimized(true)}>
          –
        </button>
      </div>

      {requirements && (
        <div className="criteria">
          {requirements.archetype_id && <span className="archetype">{requirements.archetype_id}</span>}
          {requirements.region_id && <span className="archetype region">{requirements.region_id}</span>}
          {window && (
            <span className={`chip ${requirements.field_sources.window ?? 'default'}`}>
              <span className="chip-value static">
                {formatUtc(window.start_utc).slice(0, 10)} + {Math.round(hoursBetween(window.start_utc, window.end_utc))} h
              </span>
              <span className="chip-source">
                {SOURCE_LABEL[requirements.field_sources.window ?? 'default']}
              </span>
            </span>
          )}
          {chips.map((spec) => (
            <Chip key={spec.field} spec={spec} requirements={requirements} onChange={edit} />
          ))}
        </div>
      )}

      {tab === 'chat' ? (
        <div className="chat">
          {history.length === 0 && (
            <p className="muted small">
              Describe the mission: type, dates, what it needs (light, Earth contact, flat ground).
              The AI fills the criteria above; every number in the ranking is computed by the engine.
            </p>
          )}
          {history.map((message, i) => (
            <p key={i} className={`bubble ${message.role}`}>
              {message.text}
            </p>
          ))}
          {busy && <p className="muted small">{busy}</p>}
        </div>
      ) : (
        <div className="ranking">
          {!ranking && <p className="muted small">No ranking yet: ask for sites in the chat.</p>}
          {ranking && passing.length === 0 && missing.length > 0 && (
            <p className="muted small">No site meets every constraint; the closest are below.</p>
          )}
          <ol className="rank-list">{passing.map(row)}</ol>
          {missing.length > 0 && (
            <>
              <button className="link" onClick={() => setShowMisses(!showMisses)}>
                {showMisses ? '▾' : '▸'} Miss a constraint ({missing.length}), closest first
              </button>
              {showMisses && <ol className="rank-list">{missing.map(row)}</ol>}
            </>
          )}
          {ranking && Object.keys(ranking.unavailable).length > 0 && (
            <p className="muted small" title={Object.entries(ranking.unavailable).map((e) => e.join(': ')).join('\n')}>
              Not evaluated: {Object.keys(ranking.unavailable).length} sites (hover for why).
            </p>
          )}
          {busy && <p className="muted small">{busy}</p>}
        </div>
      )}

      {error && <p className="error small">{error}</p>}

      <form
        className="ask"
        onSubmit={(event) => {
          event.preventDefault()
          void send()
        }}
      >
        <input
          value={draft}
          placeholder={history.length ? 'Add a detail…' : 'e.g. two-week robotic lander near the south pole'}
          onChange={(event) => setDraft(event.target.value)}
          disabled={busy !== null}
        />
        <button type="submit" disabled={busy !== null || !draft.trim()}>
          Send
        </button>
      </form>
    </section>
  )
}
