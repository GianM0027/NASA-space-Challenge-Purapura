// ABOUTME: Report section of the last trade-off (UI-13, D42): ranking and details per criterion, as in the popup
// ABOUTME: Owner: Federico. Values from the TradeoffResult contract; static HTML only

import { AiBadge } from '../../ai/AiBadge'
import { consistencyLabel, ordinal } from '../../compare/model'
import { formatPercent } from '../../format'
import type { SectionProps, TradeoffSectionData } from '../types'

function formatValue(value: number | null, unit: string): string {
  if (value === null) return 'n/a'
  if (unit === '') return formatPercent(value)
  return `${value.toFixed(value >= 100 ? 0 : 1)} ${unit}`
}

const METHODS = { default: 'all criteria equal', judgments: 'pairwise judgments (AHP)', direct: 'weights set directly' }

export function Tradeoff({ data, number }: SectionProps<TradeoffSectionData>) {
  const best = Math.max(...data.scores)
  const cr = consistencyLabel(data.consistency_ratio)
  return (
    <section className="rpt-section">
      <h2>{number}. Trade-off</h2>
      <h3>Ranking</h3>
      <table className="rpt-table rpt-ranking">
        <thead>
          <tr>
            <th>Place</th>
            <th>Scenario</th>
            <th>Score</th>
            <th aria-hidden="true" />
          </tr>
        </thead>
        <tbody>
          {data.ranking.map((s, position) => (
            <tr key={s} className={position === 0 ? 'rpt-best' : undefined}>
              <td>{ordinal(position)}</td>
              <td>{data.labels[s]}</td>
              <td>{data.scores[s].toFixed(3)}</td>
              <td className="rpt-bar-cell">
                <span className="rpt-bar" style={{ width: `${(100 * data.scores[s]) / best}%` }} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="rpt-note">
        Score: weighted sum of the normalized criteria (sums to 1 over the scenarios). Weights: {METHODS[data.weight_method]};
        consistency ratio {cr.text}.
      </p>
      {data.ai_comment && (
        <p className="rpt-comment">
          <AiBadge />
          {data.ai_comment}
        </p>
      )}

      <h3>Details per criterion</h3>
      <table className="rpt-table">
        <thead>
          <tr>
            <th>Criterion</th>
            <th>Weight</th>
            {data.labels.map((l) => (
              <th key={l}>{l}</th>
            ))}
            <th>Robustness</th>
          </tr>
        </thead>
        <tbody>
          {data.foms.map((f) => {
            const sens = data.sensitivity.find((x) => x.fom_id === f.id)
            const top = Math.max(...data.table.map((row) => row[f.id]?.normalized ?? 0))
            return (
              <tr key={f.id}>
                <td>
                  {f.name} {f.direction === 'higher' ? '↑' : '↓'}
                  {f.user_supplied && ' (user-supplied)'}
                </td>
                <td>{(100 * data.weights[f.id]).toFixed(0)} %</td>
                {data.table.map((row, s) => (
                  <td key={s} className={row[f.id]?.normalized === top ? 'rpt-top' : undefined}>
                    {formatValue(row[f.id]?.value ?? null, f.unit)}
                  </td>
                ))}
                <td>{sens?.min_change_percent != null ? `±${sens.min_change_percent.toFixed(0)} %` : 'robust'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <p className="rpt-note">
        ↑ more is better, ↓ less is better; bold: best scenario on that criterion. Robustness: change of that weight, in %
        of itself, that swaps two scenarios ("robust": none up to 100 %).
      </p>
    </section>
  )
}
