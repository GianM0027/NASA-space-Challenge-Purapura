// ABOUTME: Mapping between selenographic coordinates (degrees) and positions on the 3D globe
// ABOUTME: Axis convention matches a three.js SphereGeometry with an equirectangular texture

import type { GeoPoint } from '../api/contracts'

const DEG = Math.PI / 180

/**
 * Position of a lat/lon point on a sphere of the given radius.
 *
 * Axes: +X through (lat 0, lon 0), +Y through the north pole, -Z through lon 90 E. This is where
 * a three.js SphereGeometry puts an equirectangular texture whose left edge is lon -180.
 */
export function latLonToVector(
  latDeg: number,
  lonDeg: number,
  radius = 1,
): [number, number, number] {
  const lat = latDeg * DEG
  const lon = lonDeg * DEG
  return [
    radius * Math.cos(lat) * Math.cos(lon),
    radius * Math.sin(lat),
    -radius * Math.cos(lat) * Math.sin(lon),
  ]
}

/** Inverse of latLonToVector for any non-zero vector; longitude is east-positive in [-180, 180). */
export function vectorToLatLon(x: number, y: number, z: number): GeoPoint {
  const length = Math.hypot(x, y, z)
  const lon = Math.atan2(-z, x) / DEG
  return {
    lat_deg: Math.asin(y / length) / DEG,
    lon_deg: lon >= 180 ? lon - 360 : lon,
    height_m: null,
  }
}
