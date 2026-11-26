// ABOUTME: Tests of the account panel (decision D45): visitor, guest with sites, member, admin
// ABOUTME: Owner: Gian. Server-side rendering, no DOM needed

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { ProposalInfo } from '../api/client'
import { AccountPanel } from './AccountPanel'

const noop = () => undefined

const proposal: ProposalInfo = {
  id: 1,
  username: 'gian',
  site: {
    id: 'user-rim',
    name: 'Quiet Rim',
    location: { lat_deg: -85, lon_deg: 30, height_m: null },
    origin: 'user',
    status: 'custom',
    mission: null,
    agency: null,
    landing_date_utc: null,
    landing_ellipse_m: null,
    description: '',
    sources: [],
  },
  note: '',
  status: 'rejected',
  created_at: '2026-11-26T00:00:00Z',
  decided_at: '2026-11-27T00:00:00Z',
  admin_note: 'Already in the catalog.',
  community_site_id: null,
}

describe('AccountPanel', () => {
  it('offers log in and sign up to a visitor, saying accounts are optional', () => {
    const html = renderToStaticMarkup(<AccountPanel account={null} proposals={[]} savedCount={0} onChanged={noop} />)
    expect(html).toContain('Optional')
    expect(html).toContain('Create account')
    expect(html).toContain('type="password"')
  })

  it('warns a guest that their saved sites will be lost', () => {
    const html = renderToStaticMarkup(
      <AccountPanel account={{ username: null, is_guest: true, is_admin: false }} proposals={[]} savedCount={2} onChanged={noop} />,
    )
    expect(html).toContain('Your 2 saved sites will be lost when you close the browser')
  })

  it('shows a member their name, proposals with the reviewer note, and no admin tools', () => {
    const html = renderToStaticMarkup(
      <AccountPanel
        account={{ username: 'gian', is_guest: false, is_admin: false }}
        proposals={[proposal]}
        savedCount={1}
        onChanged={noop}
      />,
    )
    expect(html).toContain('Logged in as <strong>gian</strong>')
    expect(html).toContain('Quiet Rim')
    expect(html).toContain('not added')
    expect(html).toContain('Already in the catalog.')
    expect(html).not.toContain('Review proposals')
  })

  it('gives the admin the review tools', () => {
    const html = renderToStaticMarkup(
      <AccountPanel account={{ username: 'gian', is_guest: false, is_admin: true }} proposals={[]} savedCount={0} onChanged={noop} />,
    )
    expect(html).toContain('Review proposals')
    expect(html).toContain('admin')
  })

  it('puts log out and delete side by side at the bottom, after the admin tools', () => {
    const html = renderToStaticMarkup(
      <AccountPanel account={{ username: 'gian', is_guest: false, is_admin: true }} proposals={[]} savedCount={0} onChanged={noop} />,
    )
    const review = html.indexOf('Review proposals')
    const actions = html.indexOf('account-actions')
    expect(review).toBeGreaterThan(-1)
    expect(actions).toBeGreaterThan(review)
    expect(html.indexOf('Log out')).toBeGreaterThan(actions)
    expect(html.indexOf('Delete account')).toBeGreaterThan(html.indexOf('Log out'))
  })
})
