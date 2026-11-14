# ABOUTME: Sky state for the 3D globe: subsolar and sub-Earth points from an ephemeris provider
# ABOUTME: Owner: Gian. Uses only EphemerisProvider.sun_earth: nothing extra for its owner

"""Subsolar and sub-Earth points on the Moon at a given time (spec UI-1).

The globe needs the direction of the Sun and of the Earth in the Moon-fixed frame. They are
obtained from the topocentric azimuth and elevation seen from the origin (lat 0, lon 0), where
the local axes coincide with the Moon-fixed ones: up = +X (toward lat 0, lon 0), east = +Y
(toward lon 90 E), north = +Z. The sub-point is where that direction pierces the sphere.

Accuracy: the observer is on the surface, not at the Moon's center, so the result carries the
body's parallax over one lunar radius: about 0.26 degrees for the Earth (1737 km / 384400 km)
and 0.0007 degrees for the Sun. Fine for lighting a globe; site metrics never use these values.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from lunarnav.contracts import EphemerisProvider, GeoPoint, SkyState, TimeWindow

_ORIGIN = GeoPoint(lat_deg=0.0, lon_deg=0.0, height_m=0.0)


def sub_point_from_origin(azimuth_deg: float, elevation_deg: float) -> tuple[float, float]:
    """Return the sub-point of a body seen from (lat 0, lon 0) at the given direction.

    Args:
        azimuth_deg: Azimuth from north, clockwise, degrees.
        elevation_deg: Elevation above the local horizontal, degrees.

    Returns:
        (latitude, east longitude in [-180, 180)) of the point where the body is at the zenith,
        degrees.
    """
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)
    # Direction in Moon-fixed axes: X = up at the origin, Y = east, Z = north.
    x = math.sin(el)
    y = math.cos(el) * math.sin(az)
    z = math.cos(el) * math.cos(az)
    lat = math.degrees(math.asin(max(-1.0, min(1.0, z))))
    lon = math.degrees(math.atan2(y, x))
    return lat, (lon + 180.0) % 360.0 - 180.0


def sky_state(ephemeris: EphemerisProvider, time_utc: datetime) -> SkyState:
    """Return the subsolar and sub-Earth points at ``time_utc``.

    Args:
        ephemeris: Source of topocentric Sun and Earth directions.
        time_utc: Timezone-aware instant.

    Returns:
        The sky state; ``source`` echoes the ephemeris provenance.
    """
    # TimeWindow needs end > start; only the first sample is used.
    window = TimeWindow(start_utc=time_utc, end_utc=time_utc + timedelta(minutes=1))
    series = ephemeris.sun_earth(_ORIGIN, window)
    sun_lat, sun_lon = sub_point_from_origin(series.sun_azimuth_deg[0], series.sun_elevation_deg[0])
    earth_lat, earth_lon = sub_point_from_origin(
        series.earth_azimuth_deg[0], series.earth_elevation_deg[0]
    )
    return SkyState(
        time_utc=time_utc,
        subsolar=GeoPoint(lat_deg=sun_lat, lon_deg=sun_lon),
        sub_earth=GeoPoint(lat_deg=earth_lat, lon_deg=earth_lon),
        source=series.source,
    )
