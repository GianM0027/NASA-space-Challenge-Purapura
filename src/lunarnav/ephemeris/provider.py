# ABOUTME: HorizonsEphemerisProvider (EPH-1): the EphemerisProvider port backed by JPL Horizons
# ABOUTME: Checks the disk cache first (EPH-2), splits long windows into several Horizons requests

"""Ephemeris provider backed by the JPL Horizons API with a disk cache."""

from __future__ import annotations

from pathlib import Path

import httpx

from lunarnav.contracts import EphemerisProvider, EphemerisSeries, GeoPoint, TimeWindow
from lunarnav.ephemeris.cache import DEFAULT_CACHE_DIR, EphemerisCache
from lunarnav.ephemeris.horizons import (
    EARTH_ID,
    HORIZONS_MAX_ROWS,
    HORIZONS_SOURCE,
    SUN_ID,
    fetch_rows,
    sample_times,
    split_chunks,
    step_minutes_int,
)

HTTP_TIMEOUT_S = 120.0  # a 90,000-row reply took about 12 s in check C2


class HorizonsEphemerisProvider:
    """Topocentric Sun and Earth azimuth/elevation from JPL Horizons, cached on disk.

    Values are Horizons' airless apparent directions (light-time and aberration corrected). The
    contract asks for geometric directions; the difference is far below one arcminute, negligible
    next to the 0.53 deg solar disk (decision D24). Any window length is supported: windows longer
    than ``max_rows`` samples are fetched in several requests, one at a time.

    Args:
        cache_dir: Cache directory, or None to disable the cache.
        client: HTTP client (tests pass one with a mock transport); None creates a default one.
        max_rows: Largest number of samples per Horizons request.
    """

    def __init__(
        self,
        cache_dir: Path | None = DEFAULT_CACHE_DIR,
        client: httpx.Client | None = None,
        max_rows: int = HORIZONS_MAX_ROWS,
    ) -> None:
        """Create the provider (no network request is made here)."""
        self.cache = EphemerisCache(cache_dir) if cache_dir is not None else None
        self.client = client or httpx.Client(timeout=HTTP_TIMEOUT_S)
        self.max_rows = max_rows

    def sun_earth(self, location: GeoPoint, window: TimeWindow) -> EphemerisSeries:
        """Return topocentric Sun and Earth azimuth/elevation over the window.

        Args:
            location: Observer on the Moon (planetocentric lat, east lon, degrees; height above
                the 1737.4 km sphere, meters, None = on the sphere).
            window: Sample times; the step must be a whole number of minutes.

        Returns:
            Series aligned with start, start + step, ... up to end (inclusive). Azimuth from
            local north clockwise in [0, 360), elevation in degrees, no terrain.

        Raises:
            ValueError: If the step is not a whole number of minutes.
            HorizonsError: If Horizons fails and the window is not cached.
        """
        if self.cache is not None and (hit := self.cache.get(location, window)) is not None:
            return hit
        step = step_minutes_int(window)
        times, sun_az, sun_el, earth_az, earth_el = [], [], [], [], []
        for chunk in split_chunks(sample_times(window), self.max_rows):
            sun = fetch_rows(self.client, SUN_ID, location, chunk, step)
            earth = fetch_rows(self.client, EARTH_ID, location, chunk, step)
            times += sun.times_utc
            sun_az += sun.azimuth_deg
            sun_el += sun.elevation_deg
            earth_az += earth.azimuth_deg
            earth_el += earth.elevation_deg
        series = EphemerisSeries(
            location=location,
            times_utc=times,
            sun_azimuth_deg=sun_az,
            sun_elevation_deg=sun_el,
            earth_azimuth_deg=earth_az,
            earth_elevation_deg=earth_el,
            source=HORIZONS_SOURCE,
        )
        if self.cache is not None:
            self.cache.put(series, window)
        return series


def build_ephemeris_provider() -> EphemerisProvider:
    """Return the ephemeris provider the API wires into the app (spec IF-5).

    Returns:
        A Horizons-backed provider caching under ``data/cache/ephemeris/``.
    """
    return HorizonsEphemerisProvider()
