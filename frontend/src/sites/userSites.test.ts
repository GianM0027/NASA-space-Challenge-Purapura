// ABOUTME: Tests of the user-location helpers: coordinate ranges, id slugs, the saved Site
// ABOUTME: Known answers taken from the GeoPoint contract ranges and the Site id pattern

import { describe, expect, it } from 'vitest'
import { buildUserSite, parseCoordinates, slugify } from './userSites'

const ID_PATTERN = /^[a-z0-9][a-z0-9-]*$/

describe('parseCoordinates', () => {
  it('accepts the range edges', () => {
    expect(parseCoordinates('-90', '-180')).toEqual({ point: { lat_deg: -90, lon_deg: -180, height_m: null } })
    expect(parseCoordinates('90', '179.999')).toEqual({ point: { lat_deg: 90, lon_deg: 179.999, height_m: null } })
  })
  it('accepts a decimal comma and spaces', () =>
    expect(parseCoordinates(' -89,5 ', '45')).toEqual({ point: { lat_deg: -89.5, lon_deg: 45, height_m: null } }))
  it('rejects latitude out of range', () => expect(parseCoordinates('90.1', '0')).toHaveProperty('error'))
  it('rejects longitude 180, which is -180 in this convention', () =>
    expect(parseCoordinates('0', '180')).toHaveProperty('error'))
  it('rejects longitude below -180', () => expect(parseCoordinates('0', '-180.5')).toHaveProperty('error'))
  it('rejects empty or non-numeric input', () => {
    expect(parseCoordinates('', '0')).toHaveProperty('error')
    expect(parseCoordinates('0', 'east')).toHaveProperty('error')
  })
})

describe('slugify', () => {
  it('lowercases and joins words with single dashes', () =>
    expect(slugify('  Shackleton  Rim -- North ')).toBe('shackleton-rim-north'))
  it('folds accents', () => expect(slugify('Cratère Ünà')).toBe('cratere-una'))
  it('is empty when nothing is a letter or digit', () => expect(slugify('!!! ???')).toBe(''))
  it('caps the length without a trailing dash', () => {
    const slug = slugify(`${'a'.repeat(59)} b`)
    expect(slug.length).toBeLessThanOrEqual(60)
    expect(slug.endsWith('-')).toBe(false)
  })
})

describe('buildUserSite', () => {
  const point = { lat_deg: -89.2, lon_deg: 130, height_m: null }
  it('builds a user site whose id matches the contract pattern', () => {
    const result = buildUserSite(' My Rim ', point, ' near the ridge ')
    expect(result).toHaveProperty('site')
    if (!('site' in result)) return
    expect(result.site.id).toBe('user-my-rim')
    expect(result.site.id).toMatch(ID_PATTERN)
    expect(result.site).toMatchObject({ name: 'My Rim', origin: 'user', status: 'custom', description: 'near the ridge' })
    expect(result.site.location).toEqual(point)
  })
  it('requires a name', () => expect(buildUserSite('   ', point, '')).toHaveProperty('error'))
  it('requires a letter or digit in the name', () => expect(buildUserSite('***', point, '')).toHaveProperty('error'))
})
