// ABOUTME: Helpers for citations shown in the panels (spec UI-6)
// ABOUTME: Owner: Gian

/** The first source's provider, e.g. "LROC" from "LROC, Spacecraft Related Coordinates ...". */
export function shortSource(citation: string): string {
  return citation.split(',')[0].trim()
}
