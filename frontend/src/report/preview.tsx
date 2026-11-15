// ABOUTME: Dev-only entry of the report builder preview: real evaluation, trade-off view and builder in a dock
// ABOUTME: Owner: Federico (D42). Not part of the app bundle; the app mounts ReportBuilder from App (Gian)

import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import '../index.css'
import { api } from '../api/client'
import type { Evaluation, Site, TradeoffResult } from '../api/contracts'
import { CompareView } from '../compare/CompareView'
import { ReportBuilder } from './ReportBuilder'

const start = new Date('2026-11-14T00:00:00Z')
const window = {
  start_utc: start.toISOString(),
  end_utc: new Date(start.getTime() + 30 * 24 * 3_600_000).toISOString(),
  step_minutes: 60,
}

// oxlint-disable-next-line react/only-export-components -- dev-only entry, never hot-reloaded as a module
function Preview() {
  const [sites, setSites] = useState<Site[]>([])
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null)
  const [tradeoff, setTradeoff] = useState<TradeoffResult | null>(null)
  useEffect(() => {
    api.sites().then(setSites).catch(() => undefined)
    api
      .evaluate({
        site_id: 'im-2',
        window,
        area: { landing_precision_m: 100, operating_range_m: 2000, traverse_slope_limit_deg: 20, observer_height_above_ground_m: 2 },
      })
      .then(setEvaluation)
      .catch(() => undefined)
  }, [])
  return (
    <div className="dock" style={{ position: 'fixed' }}>
      <CompareView sites={sites} defaultWindow={window} initialSiteId="im-2" onResult={setTradeoff} />
      <ReportBuilder sites={sites} window={window} evaluation={evaluation} analyses={[]} ranking={null} tradeoff={tradeoff} />
    </div>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Preview />
  </StrictMode>,
)
