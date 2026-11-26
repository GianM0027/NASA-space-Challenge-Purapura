// ABOUTME: Account button in the top-right corner (decision D45): opens the account panel as a popover
// ABOUTME: Owner: Gian. Closed by default; closes on Escape or a click outside

import { useEffect, useRef, useState } from 'react'
import type { AccountInfo, ProposalInfo } from '../api/client'
import { AccountPanel } from './AccountPanel'

function PersonIcon() {
  return (
    <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
      <circle cx="10" cy="7" r="3.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path d="M3.5 17c.8-3.2 3.4-5 6.5-5s5.7 1.8 6.5 5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}

/** The corner button and its popover; same props as `AccountPanel`. */
export function AccountMenu(props: {
  account: AccountInfo | null
  proposals: ProposalInfo[]
  savedCount: number
  onChanged: () => void
}) {
  const { account } = props
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && setOpen(false)
    const onPointer = (event: PointerEvent) => {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onPointer)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', onPointer)
    }
  }, [open])

  const registered = account !== null && !account.is_guest
  // A guest with saved sites gets a dot: those sites are lost unless they create an account.
  const unsaved = account?.is_guest === true && props.savedCount > 0
  const label = registered ? account.username : 'Log in'

  return (
    <div className="account-menu" ref={root}>
      <button
        className={`account-button${open ? ' active' : ''}`}
        aria-haspopup="dialog"
        aria-expanded={open}
        title={registered ? `Account: ${account.username}` : 'Log in or create an account'}
        onClick={() => setOpen(!open)}
      >
        <PersonIcon />
        <span className="account-button-label">{label}</span>
        {unsaved && <i className="account-dot" aria-label="Saved sites not kept yet" />}
      </button>
      {open && (
        <div className="account-popover" role="dialog" aria-label="Account">
          <AccountPanel {...props} />
        </div>
      )}
    </div>
  )
}
