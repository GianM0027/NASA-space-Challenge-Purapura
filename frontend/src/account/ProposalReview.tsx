// ABOUTME: Admin review of site proposals (decision D45): approve (with edits) or reject with a note
// ABOUTME: Owner: Gian. Approved sites join the shared catalog for every visitor

import { useCallback, useEffect, useState } from 'react'
import { api, type ProposalInfo } from '../api/client'
import { formatCoordinates } from '../format'
import { accountError } from './errors'

function ReviewItem(props: { proposal: ProposalInfo; onDecided: () => void }) {
  const { proposal, onDecided } = props
  const [name, setName] = useState(proposal.site.name)
  const [description, setDescription] = useState(proposal.site.description)
  const [sources, setSources] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function decide(approve: boolean) {
    setBusy(true)
    setError(null)
    try {
      if (approve) {
        await api.approveProposal(proposal.id, {
          name,
          description,
          sources: sources
            .split('\n')
            .map((line) => line.trim())
            .filter(Boolean),
          admin_note: note,
        })
      } else {
        await api.rejectProposal(proposal.id, note)
      }
      onDecided()
    } catch (reason) {
      setError(accountError(reason))
    } finally {
      setBusy(false)
    }
  }

  return (
    <li className="review-item">
      <p className="small">
        <strong>{proposal.site.name}</strong> · {formatCoordinates(proposal.site.location)} · by {proposal.username}
      </p>
      {proposal.note && <p className="small review-note">“{proposal.note}”</p>}
      <input value={name} aria-label="Catalog name" onChange={(e) => setName(e.target.value)} />
      <input
        value={description}
        aria-label="Catalog description"
        placeholder="Description"
        onChange={(e) => setDescription(e.target.value)}
      />
      <textarea
        value={sources}
        rows={2}
        aria-label="Sources, one per line"
        placeholder="Sources, one per line (optional: otherwise the proposal is cited)"
        onChange={(e) => setSources(e.target.value)}
      />
      <input
        value={note}
        aria-label="Note to the proposer"
        placeholder="Note to the proposer (optional)"
        onChange={(e) => setNote(e.target.value)}
      />
      <div className="row">
        <button className="primary" disabled={busy || !name.trim()} onClick={() => void decide(true)}>
          Approve
        </button>
        <button disabled={busy} onClick={() => void decide(false)}>
          Reject
        </button>
      </div>
      {error && <p className="error small">{error}</p>}
    </li>
  )
}

/** Pending proposals for the admin; `onChanged` refreshes the catalog after a decision. */
export function ProposalReview(props: { onChanged: () => void }) {
  const { onChanged } = props
  const [pending, setPending] = useState<ProposalInfo[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    api
      .adminProposals('pending')
      .then(setPending)
      .catch((reason: unknown) => setError(accountError(reason)))
  }, [])
  useEffect(load, [load])

  if (error) return <p className="error small">{error}</p>
  if (pending === null) return <p className="muted small">Loading…</p>
  if (pending.length === 0) return <p className="muted small">No proposals waiting for review.</p>
  return (
    <ul className="review-list">
      {pending.map((proposal) => (
        <ReviewItem
          key={proposal.id}
          proposal={proposal}
          onDecided={() => {
            load()
            onChanged()
          }}
        />
      ))}
    </ul>
  )
}
