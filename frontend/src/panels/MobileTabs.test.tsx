// ABOUTME: Tests of the phone tab bar: three sections, the active one marked, a dot for a new result
// ABOUTME: Owner: Gian. Server-side rendering, no DOM needed

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { MobileTabs } from './MobileTabs'

const noop = () => undefined

describe('MobileTabs', () => {
  it('shows Moon, Sites and Analysis with the active tab marked', () => {
    const html = renderToStaticMarkup(<MobileTabs tab="sites" unseen={false} onTab={noop} />)
    for (const label of ['Moon', 'Sites', 'Analysis']) expect(html).toContain(label)
    expect(html.match(/aria-current="page"/g)).toHaveLength(1)
    expect(html).toMatch(/class="active" aria-current="page">.*Sites/)
    expect(html).not.toContain('mobile-tab-dot')
  })

  it('puts a dot on Analysis when a new result waits there', () => {
    const html = renderToStaticMarkup(<MobileTabs tab="globe" unseen={true} onTab={noop} />)
    expect(html).toContain('mobile-tab-dot')
  })
})
