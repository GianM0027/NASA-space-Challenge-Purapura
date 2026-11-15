// ABOUTME: Pure rules of the report builder (UI-13, D42): which sections exist, which are printable, their order
// ABOUTME: Owner: Federico. No React here, so the selection logic is unit-tested

import type { ReportInputs, SectionId } from './types'

/** Sections in print order, with the checkbox label. */
export const SECTIONS: { id: SectionId; title: string }[] = [
  { id: 'cover', title: 'Cover and mission parameters' },
  { id: 'site', title: 'Site evaluation' },
  { id: 'analysis', title: 'Mission analysis' },
  { id: 'ranking', title: 'AI assistant ranking' },
  { id: 'tradeoff', title: 'Trade-off' },
  { id: 'sources', title: 'Sources and methods' },
]

/** True when the session has produced the output a section prints. Cover and sources are always available. */
export function isAvailable(id: SectionId, inputs: ReportInputs): boolean {
  switch (id) {
    case 'site':
      return inputs.evaluation !== null
    case 'analysis':
      return inputs.analyses.some((tab) => tab.report !== null)
    case 'ranking':
      return inputs.ranking !== null && inputs.ranking.results.length > 0
    case 'tradeoff':
      return inputs.tradeoff !== null
    default:
      return true
  }
}

/** Sections to print: checked and available, in print order, numbered from 1. */
export function selectedSections(
  inputs: ReportInputs,
  checked: ReadonlySet<SectionId>,
): { id: SectionId; title: string; number: number }[] {
  return SECTIONS.filter((s) => checked.has(s.id) && isAvailable(s.id, inputs)).map((s, k) => ({ ...s, number: k + 1 }))
}

/** Default checkboxes: every available section. */
export function defaultChecked(inputs: ReportInputs): Set<SectionId> {
  return new Set(SECTIONS.filter((s) => isAvailable(s.id, inputs)).map((s) => s.id))
}
