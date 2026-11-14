// ABOUTME: Tests of the display formatters for durations, coordinates and UTC date inputs
// ABOUTME: Known answers; these strings are what a mission planner reads on screen

import { describe, expect, it } from 'vitest'
import { formatCoordinates, formatDuration, fromInputValue, hoursBetween, toInputValue } from './format'

describe('formatDuration', () => {
  it('shows minutes below one hour', () => expect(formatDuration(0.5)).toBe('30 min'))
  it('shows hours below one day', () => expect(formatDuration(5)).toBe('5 h'))
  it('shows days and hours', () => expect(formatDuration(76)).toBe('3 d 4 h'))
  it('drops zero hours', () => expect(formatDuration(48)).toBe('2 d'))
})

describe('formatCoordinates', () => {
  it('uses hemisphere letters', () =>
    expect(formatCoordinates({ lat_deg: -89.5, lon_deg: 23.47 })).toBe('89.50° S, 23.47° E'))
  it('handles north and west', () =>
    expect(formatCoordinates({ lat_deg: 26.13, lon_deg: -3.63 })).toBe('26.13° N, 3.63° W'))
})

describe('UTC date input', () => {
  it('round trips an ISO instant through the input value', () => {
    expect(toInputValue('2027-01-05T08:30:00Z')).toBe('2027-01-05T08:30')
    expect(fromInputValue('2027-01-05T08:30')).toBe('2027-01-05T08:30:00.000Z')
  })
})

describe('hoursBetween', () => {
  it('measures elapsed hours', () =>
    expect(hoursBetween('2027-01-01T00:00:00Z', '2027-01-02T06:00:00Z')).toBe(30))
})
