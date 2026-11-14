// ABOUTME: Tests of the globe coordinate mapping between selenographic lat/lon and 3D positions
// ABOUTME: Known answers for the axes, plus round trips; a sign error here misplaces every site

import { describe, expect, it } from 'vitest'
import { latLonToVector, vectorToLatLon } from './geo'

const close = (actual: number[], expected: number[]) =>
  actual.forEach((value, i) => expect(value).toBeCloseTo(expected[i], 9))

describe('latLonToVector', () => {
  it('puts lat 0, lon 0 (sub-Earth point) on +X', () => close(latLonToVector(0, 0), [1, 0, 0]))
  it('puts the north pole on +Y', () => close(latLonToVector(90, 0), [0, 1, 0]))
  it('puts lon 90 E on -Z (matches the texture wrap of a three.js sphere)', () =>
    close(latLonToVector(0, 90), [0, 0, -1]))
  it('puts lon 90 W on +Z', () => close(latLonToVector(0, -90), [0, 0, 1]))
  it('scales by the radius', () => close(latLonToVector(0, 180, 2), [-2, 0, 0]))
})

describe('vectorToLatLon', () => {
  it('inverts latLonToVector', () => {
    for (const [lat, lon] of [[-89.5, 0], [26.13, 3.63], [-43.3, -152.2], [0.67, 23.47]]) {
      const [x, y, z] = latLonToVector(lat, lon, 1.7)
      const point = vectorToLatLon(x, y, z)
      expect(point.lat_deg).toBeCloseTo(lat, 9)
      expect(point.lon_deg).toBeCloseTo(lon, 9)
    }
  })
  it('returns east longitude in [-180, 180)', () => {
    expect(vectorToLatLon(-1, 0, 0).lon_deg).toBe(-180)
  })
})
