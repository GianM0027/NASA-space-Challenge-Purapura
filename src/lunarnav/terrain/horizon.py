# ABOUTME: Terrain horizon by ray casting on the lunar sphere, curvature included (TER-1)
# ABOUTME: Pure numpy functions: great-circle destinations and the max elevation angle per azimuth

"""Terrain horizon elevation around an observer, by ray casting over a DEM.

For every azimuth we walk along the great circle leaving the observer, read the terrain height
every ``step_m`` meters up to ``max_distance_m``, and compute the elevation angle under which
the observer sees each terrain point. The horizon at that azimuth is the largest angle.

Geometry, with R the reference radius, h the terrain height, h0 the observer height and
theta = distance / R the angle at the Moon's center between observer and terrain point::

    horizontal = (R + h) sin(theta)
    vertical   = (R + h) cos(theta) - (R + h0)
    elevation  = atan2(vertical, horizontal)

The cos(theta) term is the curvature drop: about 2.9 km at 100 km on the Moon, so flat terrain
gives a slightly negative horizon.
"""

from __future__ import annotations

import numpy as np

from lunarnav.terrain.dem import MOON_RADIUS_M, Dem


def destination(
    lat_deg: float, lon_deg: float, azimuth_deg: np.ndarray, distance_m: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Points reached along great circles from one start point.

    Args:
        lat_deg: Start latitude, degrees.
        lon_deg: Start east longitude, degrees.
        azimuth_deg: Initial headings from local north, clockwise, degrees, shape (n_az,).
        distance_m: Distances along the reference sphere, meters, shape (n_d,).

    Returns:
        (latitudes, longitudes) in degrees, shape (n_az, n_d), longitudes in [-180, 180).
    """
    phi1, lam1 = np.radians(lat_deg), np.radians(lon_deg)
    az = np.radians(azimuth_deg)[:, None]
    delta = (np.asarray(distance_m, float) / MOON_RADIUS_M)[None, :]
    sin_phi2 = np.sin(phi1) * np.cos(delta) + np.cos(phi1) * np.sin(delta) * np.cos(az)
    phi2 = np.arcsin(np.clip(sin_phi2, -1.0, 1.0))
    lam2 = lam1 + np.arctan2(
        np.sin(az) * np.sin(delta) * np.cos(phi1), np.cos(delta) - np.sin(phi1) * sin_phi2
    )
    lon2 = (np.degrees(lam2) + 180.0) % 360.0 - 180.0
    return np.degrees(phi2), lon2


def elevation_angle_deg(
    distance_m: np.ndarray, terrain_height_m: np.ndarray, observer_height_m: float
) -> np.ndarray:
    """Elevation angle of terrain points seen from the observer, curvature included.

    Args:
        distance_m: Distance along the reference sphere, meters.
        terrain_height_m: Terrain height above the reference sphere, meters (broadcasts).
        observer_height_m: Observer height above the reference sphere, meters.

    Returns:
        Elevation above the observer's local horizontal plane, degrees.
    """
    theta = np.asarray(distance_m, float) / MOON_RADIUS_M
    r = MOON_RADIUS_M + np.asarray(terrain_height_m, float)
    vertical = r * np.cos(theta) - (MOON_RADIUS_M + observer_height_m)
    return np.degrees(np.arctan2(vertical, r * np.sin(theta)))


def horizon_profile(
    dem: Dem,
    lat_deg: float,
    lon_deg: float,
    observer_height_m: float,
    max_distance_m: float,
    step_m: float | None = None,
    n_azimuth: int = 360,
) -> tuple[np.ndarray, np.ndarray]:
    """Terrain horizon elevation for evenly spaced azimuths.

    Args:
        dem: Height model covering the disk of ``max_distance_m`` around the observer.
        lat_deg: Observer latitude, degrees.
        lon_deg: Observer east longitude, degrees.
        observer_height_m: Observer height above the reference sphere, meters.
        max_distance_m: Farthest terrain distance considered, meters.
        step_m: Spacing of samples along each ray, meters; default one DEM pixel.
        n_azimuth: Number of azimuths, evenly spaced from 0 (north) clockwise.

    Returns:
        (azimuths in degrees, horizon elevations in degrees), both shape (n_azimuth,).

    Raises:
        ValueError: If ``max_distance_m`` is smaller than one step.
    """
    step = dem.resolution_m if step_m is None else step_m
    if max_distance_m < step:
        raise ValueError(f"max_distance_m {max_distance_m} is below the ray step {step}")
    azimuth = np.arange(n_azimuth) * (360.0 / n_azimuth)
    distance = np.arange(1, int(max_distance_m // step) + 1) * step
    lat, lon = destination(lat_deg, lon_deg, azimuth, distance)
    angle = elevation_angle_deg(distance[None, :], dem.height_m(lat, lon), observer_height_m)
    return azimuth, angle.max(axis=1)
