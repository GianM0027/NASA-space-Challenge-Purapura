// ABOUTME: Tests of the account corner button (decision D45): closed by default, name when logged in
// ABOUTME: Owner: Gian. Server-side rendering, no DOM needed

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { AccountMenu } from './AccountMenu'

const noop = () => undefined

describe('AccountMenu', () => {
  it('starts closed: only the button, no form', () => {
    const html = renderToStaticMarkup(<AccountMenu account={null} proposals={[]} savedCount={0} onChanged={noop} />)
    expect(html).toContain('aria-expanded="false"')
    expect(html).toContain('Log in')
    expect(html).not.toContain('type="password"')
  })

  it('shows the username of a member', () => {
    const html = renderToStaticMarkup(
      <AccountMenu account={{ username: 'GianM0027', is_guest: false, is_admin: true }} proposals={[]} savedCount={0} onChanged={noop} />,
    )
    expect(html).toContain('GianM0027')
  })

  it('marks a guest whose saved sites are not kept yet', () => {
    const html = renderToStaticMarkup(
      <AccountMenu account={{ username: null, is_guest: true, is_admin: false }} proposals={[]} savedCount={1} onChanged={noop} />,
    )
    expect(html).toContain('account-dot')
  })
})
