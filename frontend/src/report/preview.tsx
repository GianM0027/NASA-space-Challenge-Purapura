// ABOUTME: Dev-only entry of the report builder preview: real evaluation, analysis, ranking, trade-off view, builder
// ABOUTME: Owner: Federico (D42). Not part of the app bundle; the app mounts ReportBuilder from App (Gian)

import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import '../index.css'
import { api } from '../api/client'
import type { AnalysisTab } from '../analysis/MissionAnalysisBox'
import type { Evaluation, Site, SiteRanking, TradeoffResult } from '../api/contracts'
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
  const [ranking, setRanking] = useState<SiteRanking | null>(null)
  const [analyses, setAnalyses] = useState<AnalysisTab[]>([])
  useEffect(() => {
    const area = { landing_precision_m: 100, operating_range_m: 2000, traverse_slope_limit_deg: 20, observer_height_above_ground_m: 2 }
    api.sites().then(setSites).catch(() => undefined)
    api.evaluate({ site_id: 'im-2', window, area }).then(setEvaluation).catch(() => undefined)
    api.rank({ window, area, min_illumination_fraction: 0.3 }).then(setRanking).catch(() => undefined)
    api
      .missionAnalysis({ site_id: 'im-2', window, area })
      .then((report) =>
        setAnalyses([
          {
            id: 'im-2',
            label: 'IM-2 Athena',
            window,
            landingPrecisionM: 100,
            center: { lat_deg: -84.79, lon_deg: 29.2, height_m: null },
            report,
            commentDone: true,
            error: null,
          },
        ]),
      )
      .catch(() => undefined)
  }, [])
  return (
    <div className="dock" style={{ position: 'fixed' }}>
      <CompareView sites={sites} defaultWindow={window} initialSiteId="im-2" onResult={setTradeoff} />
      <ReportBuilder sites={sites} window={window} evaluation={evaluation} analyses={analyses} ranking={ranking} tradeoff={tradeoff} />
    </div>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Preview />
  </StrictMode>,
)
