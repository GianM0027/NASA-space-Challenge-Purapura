// ABOUTME: Account panel (decision D45): log in, create an account, log out, delete it, see proposals
// ABOUTME: Owner: Gian. Accounts are optional; a guest's saved sites last for the browser session

import { useState } from 'react'
import { api, type AccountInfo, type ProposalInfo } from '../api/client'
import { accountError } from './errors'
import { ProposalReview } from './ProposalReview'
import { SiteUpdatePanel } from './SiteUpdatePanel'

const STATUS_LABEL: Record<ProposalInfo['status'], string> = {
  pending: 'waiting for review',
  approved: 'added to the catalog',
  rejected: 'not added',
}

function Credentials(props: { onDone: () => void }) {
  const { onDone } = props
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      if (mode === 'login') await api.login(username, password)
      else await api.register(username, password)
      setPassword('')
      onDone()
    } catch (reason) {
      setError(accountError(reason))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="tabs account-tabs">
        <button className={mode === 'login' ? 'active' : undefined} onClick={() => setMode('login')}>
          Log in
        </button>
        <button className={mode === 'register' ? 'active' : undefined} onClick={() => setMode('register')}>
          Create account
        </button>
      </div>
      <form
        className="account-form"
        onSubmit={(event) => {
          event.preventDefault()
          void submit()
        }}
      >
        <input
          value={username}
          autoComplete="username"
          aria-label="Username"
          placeholder="Username"
          onChange={(event) => setUsername(event.target.value)}
        />
        <input
          type="password"
          value={password}
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
          aria-label="Password"
          placeholder={mode === 'register' ? 'Password (at least 8 characters)' : 'Password'}
          onChange={(event) => setPassword(event.target.value)}
        />
        <button type="submit" className="primary" disabled={busy || !username.trim() || !password}>
          {busy ? '…' : mode === 'login' ? 'Log in' : 'Create account'}
        </button>
      </form>
      {error && <p className="error small">{error}</p>}
    </>
  )
}

function DeleteAccount(props: { onDone: () => void; onCancel: () => void }) {
  const { onDone, onCancel } = props
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  return (
    <form
      className="account-form confirm"
      onSubmit={(event) => {
        event.preventDefault()
        api
          .deleteAccount(password)
          .then(onDone)
          .catch((reason: unknown) => setError(accountError(reason)))
      }}
    >
      <p className="small">
        This deletes your account and every site saved in it. It cannot be undone. Enter your password to confirm.
      </p>
      <input
        type="password"
        value={password}
        autoComplete="current-password"
        aria-label="Password to confirm"
        placeholder="Password"
        onChange={(event) => setPassword(event.target.value)}
      />
      <div className="row">
        <button type="submit" disabled={!password}>
          Delete my account
        </button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
      {error && <p className="error small">{error}</p>}
    </form>
  )
}

/**
 * Account section of the side panel. `onChanged` reloads the account, the proposals and the
 * site list after anything that changes who is logged in or what the catalog holds.
 */
export function AccountPanel(props: {
  account: AccountInfo | null
  proposals: ProposalInfo[]
  savedCount: number
  onChanged: () => void
}) {
  const { account, proposals, savedCount, onChanged } = props
  const [deleting, setDeleting] = useState(false)
  const [reviewing, setReviewing] = useState(false)
  const [versioning, setVersioning] = useState(false)
  const registered = account !== null && !account.is_guest

  return (
    <section className="panel account">
      <h2>Account</h2>
      {!registered && (
        <>
          <p className="muted small">
            {account?.is_guest && savedCount > 0
              ? `Your ${savedCount} saved site${savedCount === 1 ? '' : 's'} will be lost when you close the browser. `
              : 'Optional: without an account, sites you save last until you close the browser. '}
            Create an account to keep them and to propose sites for the catalog.
          </p>
          <Credentials onDone={onChanged} />
        </>
      )}
      {registered && (
        <>
          <p className="account-head">
            Logged in as <strong>{account.username}</strong>
            {account.is_admin && <span className="badge">admin</span>}
          </p>
          {proposals.length > 0 && (
            <>
              <h3>Your proposals</h3>
              <ul className="proposal-list">
                {proposals.map((proposal) => (
                  <li key={proposal.id}>
                    <span>{proposal.site.name}</span>
                    <span className={`badge ${proposal.status}`}>{STATUS_LABEL[proposal.status]}</span>
                    {proposal.admin_note && <span className="site-description small">{proposal.admin_note}</span>}
                  </li>
                ))}
              </ul>
            </>
          )}
          {account.is_admin && (
            <>
              <button className="link" onClick={() => setReviewing(!reviewing)}>
                {reviewing ? '▾' : '▸'} Review proposals
              </button>
              {reviewing && <ProposalReview onChanged={onChanged} />}
              <button className="link" onClick={() => setVersioning(!versioning)}>
                {versioning ? '▾' : '▸'} Site version
              </button>
              {versioning && <SiteUpdatePanel />}
            </>
          )}
          {/* Session actions at the bottom, apart from the review tools above. */}
          <div className="account-actions">
            {deleting ? (
              <DeleteAccount
                onCancel={() => setDeleting(false)}
                onDone={() => {
                  setDeleting(false)
                  onChanged()
                }}
              />
            ) : (
              <div className="row">
                <button onClick={() => void api.logout().then(onChanged)}>Log out</button>
                <button className="danger" onClick={() => setDeleting(true)}>
                  Delete account…
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </section>
  )
}
