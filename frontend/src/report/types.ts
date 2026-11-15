// ABOUTME: Shared shapes of the PDF report (UI-13, D42): ReportBuilder props and the props of every section
// ABOUTME: Owner: Federico. Michael (MissionAnalysis) and Gian (AiRanking) write their sections against these types

import type { AnalysisTab } from '../analysis/MissionAnalysisBox'
import type { Evaluation, Site, SiteRanking, TimeWindow, TradeoffResult } from '../api/contracts'

/**
 * Everything App already holds and hands to the builder. Each field is null (or empty) until the user has
 * produced that output in the session; the matching section is then shown disabled ("Run it first").
 */
export type ReportInputs = {
  /** Catalog and user sites, to turn site ids into names. */
  sites: Site[]
  /** Window of the site panel (App `panelWindow`), printed on the cover. */
  window: TimeWindow
  /** Last site evaluation (App `outcome?.evaluation ?? null`). */
  evaluation: Evaluation | null
  /** Mission analysis tabs (App `analyses`); only tabs with a report are printable. */
  analyses: AnalysisTab[]
  /** Last AI assistant ranking (Gian adds `onRanking` to the AI box). */
  ranking: SiteRanking | null
  /** Last trade-off (CompareView `onResult`). */
  tradeoff: TradeoffResult | null
}

/**
 * ReportBuilder props. Self-contained like CompareView: it renders a "Report" pill for the App dock that opens
 * the popup (checkboxes left, live A4 preview right, "Download PDF" through window.print()).
 */
export type ReportBuilderProps = ReportInputs

export type SectionId = 'cover' | 'site' | 'analysis' | 'ranking' | 'tradeoff' | 'sources'

/**
 * Props every section component receives. `data` is the section's own input, never null: the builder renders a
 * section only when its data exists. `number` is the heading number in the printed report ("2. Landing site evaluation").
 *
 * Rendering rules, so all sections print alike:
 * - root element `<section className="rpt-section">` with an `<h2>` of `{number}. {title}` as first child;
 * - static HTML and SVG only: no buttons, inputs, fetches, timers or canvas (window.print() must see it all);
 * - use the report.css classes (`rpt-table`, `rpt-kv`, `rpt-note`, `rpt-figure`) and no fixed widths:
 *   the printable width is A4 minus margins (about 180 mm);
 * - numbers formatted with `../format` helpers, units always written.
 */
export type SectionProps<T> = { data: T; sites: Site[]; number: number }

/** Data of each section. */
export type CoverData = { title: string; window: TimeWindow; generatedUtc: string; contents: string[] }
export type SiteSectionData = Evaluation
/** Only the tabs with a report, in the order of the analysis window. */
export type MissionAnalysisData = AnalysisTab[]
export type AiRankingData = SiteRanking
export type TradeoffSectionData = TradeoffResult
export type SourcesData = { evaluation: Evaluation | null; tradeoff: TradeoffResult | null }

/** Props of the sections written outside Federico's paths (D42). */
export type MissionAnalysisSectionProps = SectionProps<MissionAnalysisData> // report/sections/MissionAnalysis.tsx, Michael
export type AiRankingSectionProps = SectionProps<AiRankingData> // report/sections/AiRanking.tsx, Gian
