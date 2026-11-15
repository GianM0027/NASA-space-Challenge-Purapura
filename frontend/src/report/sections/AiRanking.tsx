// ABOUTME: Report section "AI assistant ranking" (UI-13, D42): request, criteria and ranked sites
// ABOUTME: Owner: Gian. Static HTML for window.print(); every number comes from the SiteRanking

import { constraintsCount, fieldSpec, fieldValue, formatFieldValue, shownFields } from '../../ai/criteria'
import { formatUtc } from '../../format'
import type { AiRankingSectionProps } from '../types'

/** How many ranked sites the printed table lists; the rest are counted in a note. */
const PRINTED_SITES = 10

const SOURCE_LABEL: Record<string, string> = { user: 'user', archetype: 'archetype', region: 'region', default: 'GUI' }

/** The AI assistant ranking: what was asked, the criteria used, and the ranked sites. */
export function AiRanking({ data, sites, number }: AiRankingSectionProps) {
  const requirements = data.requirements
  const names = new Map(sites.map((site) => [site.id, site.name]))
  const window = requirements.window
  const printed = data.results.slice(0, PRINTED_SITES)
  const unavailable = Object.keys(data.unavailable).length
  return (
    <section className="rpt-section">
      <h2>{number}. AI assistant ranking</h2>
      <dl className="rpt-kv">
        {requirements.source_request && (
          <>
            <dt>Request</dt>
            <dd>{requirements.source_request}</dd>
          </>
        )}
        {requirements.archetype_id && (
          <>
            <dt>Mission type</dt>
            <dd>{requirements.archetype_id}</dd>
          </>
        )}
        {requirements.region_id && (
          <>
            <dt>Region</dt>
            <dd>{requirements.region_id}</dd>
          </>
        )}
        {window && (
          <>
            <dt>Window</dt>
            <dd>
              {formatUtc(window.start_utc)} to {formatUtc(window.end_utc)}
            </dd>
          </>
        )}
        {shownFields(requirements).map((spec) => {
          const value = fieldValue(requirements, spec.field)
          if (value === null) return null
          const source = requirements.field_sources[spec.field]
          return (
            <span key={spec.field} style={{ display: 'contents' }}>
              <dt>{spec.label}</dt>
              <dd>
                {spec.op === '=' ? '' : `${spec.op} `}
                {formatFieldValue(spec.unit, value)}
                {source && <span className="rpt-note"> ({SOURCE_LABEL[source] ?? source})</span>}
              </dd>
            </span>
          )
        })}
      </dl>
      <table className="rpt-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Landing site</th>
            <th>Constraints met</th>
            <th>Score</th>
            <th>Why (AI, numbers checked)</th>
          </tr>
        </thead>
        <tbody>
          {printed.map((score) => {
            const [met, total] = constraintsCount(score)
            return (
              <tr key={score.site_id}>
                <td>{score.rank}</td>
                <td>{names.get(score.site_id) ?? score.site_id}</td>
                <td>
                  {met} of {total}
                </td>
                <td>{score.all_constraints_met ? score.score.toFixed(2) : 'n/a'}</td>
                <td>{score.rationale ?? ''}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <p className="rpt-note">
        Every set criterion is a hard filter; landing sites that meet them all are scored 0 to 1 by the weighted share of
        headroom used (decision D33), the others follow, closest first.
        {data.results.length > PRINTED_SITES && ` ${data.results.length - PRINTED_SITES} more landing sites not listed.`}
        {unavailable > 0 && ` ${unavailable} landing sites could not be evaluated.`}
        {Object.keys(data.weights).length > 0 &&
          ` Weights: ${Object.entries(data.weights)
            .map(([field, weight]) => `${fieldSpec(field)?.label ?? field} ${weight.toFixed(2)}`)
            .join(', ')}.`}
      </p>
    </section>
  )
}
