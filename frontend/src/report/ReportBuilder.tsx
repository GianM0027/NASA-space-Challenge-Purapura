// ABOUTME: PDF report builder (UI-13, D42): dock pill, popup with section checkboxes and a live A4 preview
// ABOUTME: Owner: Federico. "Download PDF" prints only the report node (window.print(), print rules in report.css)

import { useEffect, useState, type ComponentType } from 'react'
import { createPortal } from 'react-dom'
import './report.css'
import { AiRanking } from './sections/AiRanking'
import { Cover } from './sections/Cover'
import { MissionAnalysis } from './sections/MissionAnalysis'
import { SiteEvaluation } from './sections/SiteEvaluation'
import { Sources } from './sections/Sources'
import { Tradeoff } from './sections/Tradeoff'
import { isAvailable, SECTIONS, selectedSections } from './selection'
import type { ReportBuilderProps, ReportInputs, SectionId, SectionProps } from './types'

/**
 * Section components, by id: mission analysis by Michael, AI ranking by Gian, the others by Federico (D42).
 * A section without a component here shows "coming soon" in the checkbox list.
 */
// oxlint-disable-next-line typescript/no-explicit-any -- each entry receives the data its id selects below
const COMPONENTS: Partial<Record<SectionId, ComponentType<SectionProps<any>>>> = {
  site: SiteEvaluation,
  analysis: MissionAnalysis,
  ranking: AiRanking,
  tradeoff: Tradeoff,
  sources: Sources,
}

const DEFAULT_TITLE = 'Lunar landing site report'

/** The data a section prints, picked from the builder inputs. */
function sectionData(id: SectionId, inputs: ReportInputs): unknown {
  switch (id) {
    case 'site':
      return inputs.evaluation
    case 'analysis':
      return inputs.analyses.filter((tab) => tab.report !== null)
    case 'ranking':
      return inputs.ranking
    case 'tradeoff':
      return inputs.tradeoff
    default:
      return { evaluation: inputs.evaluation, tradeoff: inputs.tradeoff }
  }
}

/** True when a section can be printed today: data exists and a component is registered. */
function printable(id: SectionId, inputs: ReportInputs): boolean {
  return isAvailable(id, inputs) && (id === 'cover' || COMPONENTS[id] !== undefined)
}

/** The printable document: the same tree in the preview and on paper. */
export function ReportDocument(props: {
  inputs: ReportInputs
  checked: ReadonlySet<SectionId>
  title: string
  generatedUtc: string
}) {
  const { inputs } = props
  const picked = selectedSections(inputs, props.checked).filter((s) => printable(s.id, inputs))
  const contents = picked.filter((s) => s.id !== 'cover').map((s) => `${s.number}. ${s.title}`)
  return (
    <article className="rpt-doc">
      {picked.map(({ id, number }) => {
        if (id === 'cover') {
          const data = { title: props.title, window: inputs.window, generatedUtc: props.generatedUtc, contents }
          return <Cover key={id} data={data} sites={inputs.sites} number={number} />
        }
        const Section = COMPONENTS[id]!
        return <Section key={id} data={sectionData(id, inputs)} sites={inputs.sites} number={number} />
      })}
      {picked.length === 0 && <p className="rpt-note">Tick at least one section.</p>}
    </article>
  )
}

export function ReportBuilder(inputs: ReportBuilderProps) {
  const [open, setOpen] = useState(false)
  // Unticked sections; every other available one is in, so a new output appears in the preview at once.
  const [excluded, setExcluded] = useState<Set<SectionId>>(new Set())
  const [title, setTitle] = useState(DEFAULT_TITLE)
  const [generatedUtc, setGeneratedUtc] = useState(() => new Date().toISOString())

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const checked = new Set(SECTIONS.map((s) => s.id).filter((id) => !excluded.has(id)))
  const toggle = (id: SectionId, on: boolean) =>
    setExcluded((old) => {
      const next = new Set(old)
      if (on) next.delete(id)
      else next.add(id)
      return next
    })
  const count = SECTIONS.filter((s) => s.id !== 'cover' && checked.has(s.id) && printable(s.id, inputs)).length

  const print = () => {
    const now = new Date().toISOString()
    setGeneratedUtc(now)
    // The browser names the PDF after the document title.
    const previous = document.title
    document.title = `${title.trim() || DEFAULT_TITLE} ${now.slice(0, 10)}`
    const restore = () => {
      document.title = previous
      window.removeEventListener('afterprint', restore)
    }
    window.addEventListener('afterprint', restore)
    // Let React paint the new timestamp before the print dialog freezes the page.
    setTimeout(() => window.print(), 50)
  }

  if (!open) {
    return (
      <button className="ai-pill rpt-pill" onClick={() => setOpen(true)}>
        Report
      </button>
    )
  }

  const doc = <ReportDocument inputs={inputs} checked={checked} title={title.trim() || DEFAULT_TITLE} generatedUtc={generatedUtc} />

  return (
    <div className="rpt-backdrop" onClick={(e) => e.target === e.currentTarget && setOpen(false)}>
      <div className="rpt-dialog" role="dialog" aria-modal="true" aria-label="PDF report">
        <header className="rpt-head">
          <div>
            <h2>PDF report</h2>
            <p className="muted small">Tick what to include: the preview on the right is exactly what the PDF will contain.</p>
          </div>
          <button onClick={() => setOpen(false)} title="Keeps your choices (Esc)">
            Minimize
          </button>
        </header>
        <div className="rpt-layout">
          <aside className="rpt-controls">
            <label className="rpt-title-field">
              Report title
              <input value={title} onChange={(e) => setTitle(e.target.value)} />
            </label>
            <ul className="rpt-checks">
              {SECTIONS.map((s) => {
                const hasData = isAvailable(s.id, inputs)
                const ready = s.id === 'cover' || COMPONENTS[s.id] !== undefined
                const enabled = hasData && ready
                return (
                  <li key={s.id} className={enabled ? undefined : 'muted'}>
                    <label>
                      <input
                        type="checkbox"
                        disabled={!enabled}
                        checked={enabled && checked.has(s.id)}
                        onChange={(e) => toggle(s.id, e.target.checked)}
                      />
                      <span>
                        {s.title}
                        {!ready && <span className="small"> · coming soon</span>}
                        {ready && !hasData && <span className="small"> · run it first</span>}
                      </span>
                    </label>
                  </li>
                )
              })}
            </ul>
            <button className="rpt-primary" onClick={print} disabled={count === 0 && !checked.has('cover')}>
              Download PDF
            </button>
            <p className="muted small">
              Opens the print dialog: choose <em>Save as PDF</em> as the printer. Tip: turn off the browser's headers and
              footers.
            </p>
          </aside>
          <div className="rpt-preview">
            <div className="rpt-paper">{doc}</div>
          </div>
        </div>
      </div>
      {createPortal(<div className="rpt-print-root">{doc}</div>, document.body)}
    </div>
  )
}
