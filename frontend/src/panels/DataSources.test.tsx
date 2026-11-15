// ABOUTME: Tests of the data sources credit: short coordinate source, closed by default
// ABOUTME: Owner: Gian

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { DataSources } from './DataSources'
import { shortSource } from './sources'

describe('shortSource', () => {
  it('keeps the provider before the first comma', () => {
    expect(shortSource('LROC, Spacecraft Related Coordinates - 2016 Update, https://x')).toBe('LROC')
    expect(shortSource('Wagner et al. 2017, Icarus 283')).toBe('Wagner et al. 2017')
    expect(shortSource('NASA')).toBe('NASA')
  })
})

describe('DataSources', () => {
  it('shows only the short credit until opened', () => {
    const html = renderToStaticMarkup(<DataSources />)
    expect(html).toContain('Data: NASA LRO · LOLA · JPL Horizons')
    expect(html).not.toContain('data-sources-popover')
  })
})
