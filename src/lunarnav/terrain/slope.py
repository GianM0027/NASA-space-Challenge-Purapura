# ABOUTME: Terrain slope statistics over a disk around a site (TER-2)
# ABOUTME: Local east/north grid at DEM spacing, finite-difference gradient, mean and max slope

"""Slope of the terrain over a disk, from a DEM.

Around the site we lay a square grid of points spaced one DEM pixel apart, in local east and
north meters, and place each point on the Moon along the great circle from the center. Heights
are read from the DEM; the slope at each point is ``atan(|grad h|)`` with the gradient taken by
central differences over the grid. Statistics use the points inside the disk.

The slope baseline is the DEM pixel (about 474 m on LDEM_64, 80 m on the polar tile), so these
are regional slopes: boulder- and crater-scale slopes that matter at touchdown are steeper.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from lunarnav.terrain.dem import MOON_RADIUS_M, Dem


@dataclass(frozen=True)
class SlopeStats:
    """Elevation and slope over a disk (module-internal; converted to TerrainStats at the edge).

    Attributes:
        elevation_m: Height of the center above the reference sphere, meters.
        slope_mean_deg: Mean slope over the disk, degrees.
        slope_max_deg: Maximum slope over the disk, degrees.
    """

    elevation_m: float
    slope_mean_deg: float
    slope_max_deg: float


def offset_points(
    lat_deg: float, lon_deg: float, east_m: np.ndarray, north_m: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Points at local east/north offsets from a center, placed along great circles.

    Args:
        lat_deg: Center latitude, degrees.
        lon_deg: Center east longitude, degrees.
        east_m: East offsets, meters (any shape).
        north_m: North offsets, meters (same shape).

    Returns:
        (latitudes, longitudes) in degrees, same shape as the offsets.
    """
    phi1, lam1 = np.radians(lat_deg), np.radians(lon_deg)
    az = np.arctan2(east_m, north_m)
    delta = np.hypot(east_m, north_m) / MOON_RADIUS_M
    sin_phi2 = np.sin(phi1) * np.cos(delta) + np.cos(phi1) * np.sin(delta) * np.cos(az)
    phi2 = np.arcsin(np.clip(sin_phi2, -1.0, 1.0))
    lam2 = lam1 + np.arctan2(
        np.sin(az) * np.sin(delta) * np.cos(phi1), np.cos(delta) - np.sin(phi1) * sin_phi2
    )
    return np.degrees(phi2), (np.degrees(lam2) + 180.0) % 360.0 - 180.0


def slope_stats(
    dem: Dem, lat_deg: float, lon_deg: float, radius_m: float, spacing_m: float | None = None
) -> SlopeStats:
    """Center elevation and slope statistics over a disk.

    Args:
        dem: Height model covering the disk plus one pixel.
        lat_deg: Disk center latitude, degrees.
        lon_deg: Disk center east longitude, degrees.
        radius_m: Disk radius, meters, >= 0 (0 means the center point only).
        spacing_m: Grid spacing and slope baseline, meters; default one DEM pixel.

    Returns:
        The statistics.

    Raises:
        ValueError: If ``radius_m`` is negative.
    """
    if radius_m < 0.0:
        raise ValueError(f"radius_m {radius_m} must be >= 0")
    step = dem.resolution_m if spacing_m is None else spacing_m
    k = int(np.ceil(radius_m / step)) + 1  # one extra ring so central differences reach the edge
    axis = np.arange(-k, k + 1) * step
    east, north = np.meshgrid(axis, axis)  # rows: north offsets, columns: east offsets
    lat, lon = offset_points(lat_deg, lon_deg, east, north)
    heights = dem.height_m(lat, lon)
    dh_dnorth, dh_deast = np.gradient(heights, step)
    slope = np.degrees(np.arctan(np.hypot(dh_deast, dh_dnorth)))
    inside = np.hypot(east, north) <= radius_m + 1e-6
    return SlopeStats(
        elevation_m=float(heights[k, k]),
        slope_mean_deg=float(slope[inside].mean()),
        slope_max_deg=float(slope[inside].max()),
    )
