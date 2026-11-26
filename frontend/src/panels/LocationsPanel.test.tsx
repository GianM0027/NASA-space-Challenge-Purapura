// ABOUTME: Tests of the coordinates box: a globe click and a typed point lead to the same save controls
// ABOUTME: Owner: Gian. Server-side rendering, no DOM needed

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { CoordinatesBox } from './LocationsPanel'

const noop = () => undefined
const save = async () => null

describe('CoordinatesBox', () => {
  it('offers saving at once for a point clicked on the globe (analyzed automatically)', () => {
    const html = renderToStaticMarkup(
      <CoordinatesBox initial={{ lat_deg: -89.5, lon_deg: 0, height_m: null }} onAnalyze={noop} onSave={save} />,
    )
    expect(html).toContain('Save as custom landing site')
  })

  it('waits for the arrow button before offering to save typed coordinates', () => {
    const html = renderToStaticMarkup(<CoordinatesBox initial={null} onAnalyze={noop} onSave={save} />)
    expect(html).not.toContain('Save as custom landing site')
    expect(html).toContain('aria-label="Analyze these coordinates"')
  })
})
