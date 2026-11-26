// ABOUTME: Tests of the admin site version panel (D46): the first render waits for the status
// ABOUTME: Owner: Gian. Server-side rendering only shows the loading state; the logic is in the API tests

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { SiteUpdatePanel } from './SiteUpdatePanel'

describe('SiteUpdatePanel', () => {
  it('starts by checking the versions', () => {
    expect(renderToStaticMarkup(<SiteUpdatePanel />)).toContain('Checking')
  })
})
