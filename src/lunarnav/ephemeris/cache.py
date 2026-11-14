# ABOUTME: Disk cache for ephemeris series (EPH-2): one JSON file per site and fetched window
# ABOUTME: A cached window also serves sub-windows on a compatible step grid (e.g. after warm-up)

"""Disk cache of ``EphemerisSeries`` under ``data/cache/ephemeris/`` (git-ignored).

Layout: ``<root>/<site key>/<start>_<end>_<step>m.json``, times as compact UTC
(``20261201T000000``). A lookup returns a stored series that contains every requested sample time,
sliced to the request, so a long warmed-up window also answers shorter windows inside it.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from lunarnav.contracts import EphemerisSeries, GeoPoint, TimeWindow
from lunarnav.ephemeris.horizons import sample_times, step_minutes_int

log = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path("data/cache/ephemeris")  # relative to the repo root (working directory)
_TIME_FMT = "%Y%m%dT%H%M%S"


class EphemerisCache:
    """Stores and retrieves ephemeris series on disk.

    Args:
        root: Cache directory; created on first write.
    """

    def __init__(self, root: Path = DEFAULT_CACHE_DIR) -> None:
        """Create a cache rooted at ``root``."""
        self.root = Path(root)

    def get(self, location: GeoPoint, window: TimeWindow) -> EphemerisSeries | None:
        """Return the cached series for ``window`` at ``location``, or None on a miss.

        Args:
            location: Observer on the Moon.
            window: Requested window; served from any stored window that contains all its sample
                times, i.e. whose step divides the requested step, with the same grid phase
                (a 1-minute warm-up serves any whole-minute window).

        Returns:
            A series aligned with the window's sample times, or None.
        """
        site_dir = self.root / _site_key(location)
        if not site_dir.is_dir():
            return None
        step = step_minutes_int(window)
        times = sample_times(window)
        for path in sorted(site_dir.glob("*m.json")):
            start, end, stored_step = _parse_name(path)
            if stored_step is None or step % stored_step:
                continue
            if start > times[0] or end < times[-1]:
                continue
            offset, rem = divmod((times[0] - start).total_seconds(), 60 * stored_step)
            if rem:
                continue  # different grid phase
            stride = step // stored_step
            series = EphemerisSeries.model_validate_json(path.read_text(encoding="utf-8"))
            sl = slice(int(offset), int(offset) + (len(times) - 1) * stride + 1, stride)
            if series.times_utc[sl] != times:
                continue
            log.info("ephemeris cache hit %s", path.name)
            return EphemerisSeries(
                location=location,
                times_utc=series.times_utc[sl],
                sun_azimuth_deg=series.sun_azimuth_deg[sl],
                sun_elevation_deg=series.sun_elevation_deg[sl],
                earth_azimuth_deg=series.earth_azimuth_deg[sl],
                earth_elevation_deg=series.earth_elevation_deg[sl],
                source=series.source,
            )
        return None

    def put(self, series: EphemerisSeries, window: TimeWindow) -> Path:
        """Store a series fetched for ``window`` and return the file path.

        Args:
            series: Series aligned with the window's sample times.
            window: Window the series was computed for.

        Returns:
            Path of the written JSON file.
        """
        site_dir = self.root / _site_key(series.location)
        site_dir.mkdir(parents=True, exist_ok=True)
        times = series.times_utc
        name = (
            f"{times[0].astimezone(UTC):{_TIME_FMT}}_{times[-1].astimezone(UTC):{_TIME_FMT}}"
            f"_{step_minutes_int(window)}m.json"
        )
        path = site_dir / name
        tmp = path.with_suffix(".tmp")
        tmp.write_text(series.model_dump_json(), encoding="utf-8")
        tmp.replace(path)  # atomic on the same filesystem: readers never see a partial file
        return path


def _site_key(location: GeoPoint) -> str:
    """Directory name for a site: rounded coordinates (1e-6 deg is about 3 cm on the Moon)."""
    height = location.height_m or 0.0
    return f"lat{location.lat_deg:+.6f}_lon{location.lon_deg:+.6f}_h{height:.1f}"


def _parse_name(path: Path) -> tuple[datetime, datetime, int | None]:
    """Return (first time, last time, step minutes) from a cache file name; step None if invalid."""
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    try:
        start, end, step = path.stem.split("_")
        return (
            datetime.strptime(start, _TIME_FMT).replace(tzinfo=UTC),
            datetime.strptime(end, _TIME_FMT).replace(tzinfo=UTC),
            int(step.removesuffix("m")),
        )
    except ValueError:
        return epoch, epoch, None
