// ABOUTME: Pure helpers for user locations: coordinate validation, id slug, the Site sent to POST /api/sites
// ABOUTME: Owner: Gian. Ranges follow the GeoPoint contract (lat [-90, 90], east-positive lon [-180, 180))

import { ApiError } from '../api/client'
import type { GeoPoint, Site } from '../api/contracts'

/** Result of parsing the coordinates box: a point, or the message to show. */
export type ParsedPoint = { point: GeoPoint } | { error: string }

/** Prefix of every user location id, so it never collides with a curated site. */
export const USER_ID_PREFIX = 'user-'

/** Upper bound on the slug length, so ids stay readable in URLs and lists. */
const MAX_SLUG_LENGTH = 60

/**
 * Parse one number typed by the user.
 *
 * @param text Raw input; surrounding spaces are ignored, a comma is accepted as decimal separator.
 * @returns The number, or null if the text is empty or not a finite number.
 */
function parseNumber(text: string): number | null {
  const cleaned = text.trim().replace(',', '.')
  if (cleaned === '') return null
  const value = Number(cleaned)
  return Number.isFinite(value) ? value : null
}

/**
 * Validate the coordinates box against the GeoPoint contract.
 *
 * @param latText Latitude in degrees, planetocentric, [-90, 90].
 * @param lonText Longitude in degrees, east-positive, [-180, 180).
 * @returns The point (height taken from the DEM), or a message naming the bad field.
 */
export function parseCoordinates(latText: string, lonText: string): ParsedPoint {
  const lat = parseNumber(latText)
  const lon = parseNumber(lonText)
  if (lat === null) return { error: 'Latitude must be a number of degrees.' }
  if (lon === null) return { error: 'Longitude must be a number of degrees.' }
  if (lat < -90 || lat > 90) return { error: 'Latitude must be between -90 and 90 degrees.' }
  if (lon < -180 || lon >= 180) {
    return { error: 'Longitude must be at least -180 and below 180 degrees, east positive (use -180 for 180 W).' }
  }
  return { point: { lat_deg: lat, lon_deg: lon, height_m: null } }
}

/**
 * Turn a display name into the id slug: lowercase ASCII letters, digits and single dashes.
 *
 * @param name Display name; accents are folded ("Shäckleton" gives "shackleton").
 * @returns The slug, possibly empty when the name has no letter or digit.
 */
export function slugify(name: string): string {
  return name
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .slice(0, MAX_SLUG_LENGTH)
    .replace(/^-+|-+$/g, '')
}

/**
 * Build the user site to save, or explain why it cannot be saved.
 *
 * @param name Display name, required.
 * @param location Point to save.
 * @param description Optional free text.
 * @returns The site for POST /api/sites (id `user-<slug>`, matching `^[a-z0-9][a-z0-9-]*$`), or a message.
 */
export function buildUserSite(
  name: string,
  location: GeoPoint,
  description: string,
): { site: Site } | { error: string } {
  const trimmed = name.trim()
  if (trimmed === '') return { error: 'Give the location a name.' }
  const slug = slugify(trimmed)
  if (slug === '') return { error: 'The name needs at least one letter or digit.' }
  return {
    site: {
      id: `${USER_ID_PREFIX}${slug}`,
      name: trimmed,
      location: { lat_deg: location.lat_deg, lon_deg: location.lon_deg, height_m: null },
      origin: 'user',
      status: 'custom',
      mission: null,
      agency: null,
      landing_date_utc: null,
      landing_ellipse_m: null,
      description: description.trim(),
      sources: [],
    },
  }
}

/**
 * Turn a failed site request into a sentence for the user.
 *
 * @param error What the API client threw.
 * @param siteId Id of the location the request was about.
 * @returns The message to show next to the control that failed.
 */
export function describeSiteError(error: unknown, siteId: string): string {
  if (!(error instanceof ApiError)) return String(error instanceof Error ? error.message : error)
  switch (error.status) {
    case 409:
      return `A location with id "${siteId}" already exists: choose another name.`
    case 404:
      return 'This location no longer exists; the list was refreshed.'
    case 403:
      return 'Curated sites cannot be renamed or deleted, only your own locations.'
    case 422:
      return `The backend rejected the input: ${error.detail}`
    case 501:
      return `Not available yet: ${error.detail}`
    default:
      return `Backend error (HTTP ${error.status}): ${error.detail}`
  }
}
