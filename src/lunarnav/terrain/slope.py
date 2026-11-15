# ABOUTME: Terrain slope statistics over a disk around a site (TER-2, decision D36)
# ABOUTME: Local east/north grid; pixel or 100 m plane-fit baseline; mean and 99th percentile max

"""Slope of the terrain over a disk, from a DEM.

Around the site we lay a square grid of points spaced one DEM pixel apart, in local east and
north meters, and place each point on the Moon along the great circle from the center. Heights
are read from the DEM and the slope at each point is ``atan(|grad h|)``.

Two slope baselines (decision D36):

* pixel baseline (default): central differences between neighbouring cells;
* 100 m baseline (landing disk): each cell's slope comes from a least-squares plane fitted to the
  heights within 50 m of it, matching the NASA landing criterion "surface slope for landing
  (100 m) < 10 deg" (NASA HLS Overview 2025, p. 21). Where cells are wider than 50 m (80 m and
  474 m DEMs) no neighbour lies within 50 m, and the pixel baseline, already >= 100 m, is used.

Every reported maximum is the 99th percentile of the cell slopes over the disk (decision D36):
the single steepest cell of a 20 m DEM is often an isolated spike.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from lunarnav.terrain.dem import MOON_RADIUS_M, Dem

# Decision D36: the reported "maximum" slope is this percentile of the cell slopes over the disk.
ROBUST_MAX_PERCENTILE = 99.0
# Decision D36: landing slopes on a 100 m baseline, i.e. a plane fitted within 50 m of each cell.
LANDING_BASELINE_M = 100.0


@dataclass(frozen=True)
class SlopeStats:
    """Elevation and slope over a disk (module-internal; converted to TerrainStats at the edge).

    Attributes:
        elevation_m: Height of the center above the reference sphere, meters.
        slope_mean_deg: Mean slope over the disk, degrees.
        slope_max_deg: Robust maximum slope over the disk (99th percentile), degrees.
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


@dataclass(frozen=True)
class SlopeGrid:
    """Heights and slopes on a local square grid centered on a site (module-internal).

    Attributes:
        east_m: East offset of each cell from the center, meters, shape (n, n).
        north_m: North offset of each cell, meters, same shape (rows go north).
        heights_m: Terrain height above the reference sphere, meters, same shape.
        slope_deg: Slope at each cell, degrees, same shape.
        step_m: Cell size, meters.
        center: Index of the center cell along both axes.
        baseline_m: Slope baseline actually used, meters (2 x step for central differences).
    """

    east_m: np.ndarray
    north_m: np.ndarray
    heights_m: np.ndarray
    slope_deg: np.ndarray
    step_m: float
    center: int
    baseline_m: float

    def inside(self, radius_m: float) -> np.ndarray:
        """Boolean mask of the cells within ``radius_m`` of the center."""
        return np.hypot(self.east_m, self.north_m) <= radius_m + 1e-6

    def disk_stats(self, radius_m: float) -> SlopeStats:
        """Center elevation, mean slope and robust maximum (99th percentile) over the disk."""
        slopes = self.slope_deg[self.inside(radius_m)]
        return SlopeStats(
            elevation_m=float(self.heights_m[self.center, self.center]),
            slope_mean_deg=float(slopes.mean()),
            slope_max_deg=float(np.percentile(slopes, ROBUST_MAX_PERCENTILE)),
        )


def slope_grid(
    dem: Dem,
    lat_deg: float,
    lon_deg: float,
    radius_m: float,
    spacing_m: float | None = None,
    baseline_m: float | None = None,
) -> SlopeGrid:
    """Heights and slopes on a local grid covering the disk of ``radius_m`` (plus a border).

    Args:
        dem: Height model covering the disk plus its border.
        lat_deg: Center latitude, degrees.
        lon_deg: Center east longitude, degrees.
        radius_m: Disk radius, meters, >= 0.
        spacing_m: Grid spacing, meters; default one DEM pixel.
        baseline_m: Slope baseline, meters: None for the pixel baseline (central differences),
            or a length whose half is the radius of the plane fit around each cell (D36).

    Returns:
        The grid.

    Raises:
        ValueError: If ``radius_m`` is negative.
    """
    if radius_m < 0.0:
        raise ValueError(f"radius_m {radius_m} must be >= 0")
    step = dem.resolution_m if spacing_m is None else spacing_m
    fit_radius = 0.0 if baseline_m is None else baseline_m / 2.0
    border = max(1, int(np.ceil(fit_radius / step)))  # cells needed around the disk edge
    k = int(np.ceil(radius_m / step)) + border
    axis = np.arange(-k, k + 1) * step
    east, north = np.meshgrid(axis, axis)  # rows: north offsets, columns: east offsets
    lat, lon = offset_points(lat_deg, lon_deg, east, north)
    heights = dem.height_m(lat, lon)
    offsets = _fit_offsets(step, fit_radius)
    if offsets:
        dh_deast, dh_dnorth = _plane_fit_gradient(heights, offsets, step)
        used = float(baseline_m)
    else:  # cells wider than the fit radius: no neighbour inside it, use the pixel baseline
        dh_dnorth, dh_deast = np.gradient(heights, step)
        used = 2.0 * step
    slope = np.degrees(np.arctan(np.hypot(dh_deast, dh_dnorth)))
    return SlopeGrid(east, north, heights, slope, step, k, used)


def slope_stats(
    dem: Dem, lat_deg: float, lon_deg: float, radius_m: float, spacing_m: float | None = None
) -> SlopeStats:
    """Center elevation and slope statistics over a disk (pixel baseline).

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
    return slope_grid(dem, lat_deg, lon_deg, radius_m, spacing_m).disk_stats(radius_m)


def _fit_offsets(step_m: float, fit_radius_m: float) -> list[tuple[int, int]]:
    """Cell offsets (row, col) within ``fit_radius_m``; empty when only the cell itself fits."""
    n = int(fit_radius_m // step_m)
    offsets = [
        (i, j)
        for i in range(-n, n + 1)
        for j in range(-n, n + 1)
        if np.hypot(i * step_m, j * step_m) <= fit_radius_m + 1e-9
    ]
    return offsets if len(offsets) > 1 else []


def _plane_fit_gradient(
    heights: np.ndarray, offsets: list[tuple[int, int]], step_m: float
) -> tuple[np.ndarray, np.ndarray]:
    """East and north gradients of the least-squares plane fitted around every cell.

    The neighbourhood is symmetric, so the fit decouples: d/deast = sum(dx z) / sum(dx^2) and
    likewise north. Borders are padded by repeating the edge cells.
    """
    n = max(max(abs(i), abs(j)) for i, j in offsets)
    padded = np.pad(heights, n, mode="edge")
    rows, cols = heights.shape
    sum_xz = np.zeros(heights.shape)
    sum_yz = np.zeros(heights.shape)
    sum_xx = sum_yy = 0.0
    for i, j in offsets:
        z = padded[n + i : n + i + rows, n + j : n + j + cols]
        dx, dy = j * step_m, i * step_m  # columns go east, rows go north
        sum_xz += dx * z
        sum_yz += dy * z
        sum_xx += dx * dx
        sum_yy += dy * dy
    return sum_xz / sum_xx, sum_yz / sum_yy
