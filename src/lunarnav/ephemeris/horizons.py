# ABOUTME: Low-level JPL Horizons API access: query parameters, sample grid, chunking, parsing
# ABOUTME: Used by HorizonsEphemerisProvider; no caching here (see cache.py)

"""JPL Horizons API helpers for topocentric observers on the Moon.

Horizons is queried in OBSERVER mode with the observer at a geodetic site on the Moon
(``CENTER='coord@301'``) and quantity 4 (airless apparent azimuth and elevation, degrees, azimuth
from north clockwise). Times are UTC. See https://ssd-api.jpl.nasa.gov/doc/horizons.html and
decision D24 in docs/decisions.md.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

from lunarnav.contracts import GeoPoint, TimeWindow

log = logging.getLogger(__name__)

HORIZONS_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
HORIZONS_SOURCE = "JPL Horizons API (airless apparent az/el, quantity 4)"
SUN_ID = "10"  # Horizons major-body id of the Sun
EARTH_ID = "399"  # Horizons major-body id of the Earth (body center, not the barycenter)
MOON_CENTER = "coord@301"  # topocentric observer on body 301 (Moon), Mean Earth frame
# Horizons rejects requests above 90,000 output rows ("Output length exceeded ... max. is 90000",
# measured in check C2); keep a margin.
HORIZONS_MAX_ROWS = 80_000

_MONTHS = {
    m: i
    for i, m in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1
    )
}


class HorizonsError(RuntimeError):
    """Horizons could not be reached or returned no ephemeris (message includes its reply)."""


@dataclass(frozen=True)
class AzElRows:
    """Parsed Horizons ephemeris rows for one target.

    Attributes:
        times_utc: Sample times, timezone-aware UTC.
        azimuth_deg: Azimuth from local north, clockwise, degrees, [0, 360).
        elevation_deg: Elevation above the local horizontal, degrees.
    """

    times_utc: list[datetime]
    azimuth_deg: list[float]
    elevation_deg: list[float]


def step_minutes_int(window: TimeWindow) -> int:
    """Return the window step as whole minutes (Horizons accepts only integer minute steps).

    Raises:
        ValueError: If the step is not a whole number of minutes.
    """
    step = window.step_minutes
    if abs(step - round(step)) > 1e-9:
        raise ValueError(f"step_minutes {step} must be a whole number of minutes for Horizons")
    return round(step)


def sample_times(window: TimeWindow) -> list[datetime]:
    """Return the sample times of a window: start, start + step, ... up to end (inclusive).

    Args:
        window: Time window; its step must be a whole number of minutes.

    Returns:
        Timezone-aware UTC datetimes, truncated to whole seconds.
    """
    step = timedelta(minutes=step_minutes_int(window))
    start = _to_utc(window.start_utc)
    end = _to_utc(window.end_utc)
    n = int((end - start) / step) + 1
    return [start + i * step for i in range(n)]


def split_chunks(times: list[datetime], max_rows: int = HORIZONS_MAX_ROWS) -> list[list[datetime]]:
    """Split sample times into consecutive, balanced chunks of at most ``max_rows`` samples.

    Args:
        times: Sample times in increasing order.
        max_rows: Largest number of rows one Horizons request may return.

    Returns:
        The chunks, in order; their concatenation equals ``times``.
    """
    if max_rows < 1:
        raise ValueError(f"max_rows must be >= 1, got {max_rows}")
    n_chunks = max(1, math.ceil(len(times) / max_rows))
    size, extra = divmod(len(times), n_chunks)
    chunks, i = [], 0
    for k in range(n_chunks):
        j = i + size + (1 if k < extra else 0)
        chunks.append(times[i:j])
        i = j
    return chunks


def build_params(
    target: str, location: GeoPoint, start: datetime, stop: datetime, step_minutes: int
) -> dict[str, str]:
    """Return the Horizons API query parameters for one target and one time range.

    Args:
        target: Horizons body id (e.g. ``SUN_ID``).
        location: Observer on the Moon; ``height_m`` None means on the 1737.4 km reference sphere.
        start: First sample, UTC.
        stop: Last sample, UTC (Horizons includes it when it falls on the step grid).
        step_minutes: Step, whole minutes.

    Returns:
        Query parameters, values quoted as Horizons expects.
    """
    height_km = (location.height_m or 0.0) / 1000.0
    site = f"{location.lon_deg:.6f},{location.lat_deg:.6f},{height_km:.4f}"  # E-lon, lat, alt km
    return {
        "format": "json",
        "COMMAND": f"'{target}'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "CENTER": f"'{MOON_CENTER}'",
        "COORD_TYPE": "'GEODETIC'",
        "SITE_COORD": f"'{site}'",
        "START_TIME": f"'{_fmt(start)}'",
        "STOP_TIME": f"'{_fmt(stop)}'",
        "STEP_SIZE": f"'{step_minutes}m'",
        "QUANTITIES": "'4'",
        "ANG_FORMAT": "'DEG'",
        "APPARENT": "'AIRLESS'",
        "CSV_FORMAT": "'YES'",
        "TIME_DIGITS": "'SECONDS'",
    }


def parse_result(result: str) -> AzElRows:
    """Parse the ``result`` text of a Horizons quantity-4 CSV ephemeris.

    Args:
        result: The ``result`` field of the Horizons JSON reply.

    Returns:
        The parsed rows.

    Raises:
        HorizonsError: If the text has no ``$$SOE``/``$$EOE`` block (Horizons reported an error)
            or a row cannot be parsed.
    """
    soe, eoe = result.find("$$SOE"), result.find("$$EOE")
    if soe < 0 or eoe < soe:
        raise HorizonsError(f"Horizons returned no ephemeris: {result.strip()[:500]}")
    times, az, el = [], [], []
    for line in result[soe + 5 : eoe].strip().splitlines():
        cols = [c.strip() for c in line.split(",")]
        try:
            times.append(_parse_time(cols[0]))
            az.append(float(cols[3]) % 360.0)
            el.append(float(cols[4]))
        except (IndexError, KeyError, ValueError) as exc:
            raise HorizonsError(f"cannot parse Horizons row {line!r}") from exc
    return AzElRows(times, az, el)


def fetch_rows(
    client: httpx.Client,
    target: str,
    location: GeoPoint,
    times: list[datetime],
    step_minutes: int,
) -> AzElRows:
    """Query Horizons for one chunk of sample times and return exactly those rows.

    Args:
        client: HTTP client used for the request.
        target: Horizons body id.
        location: Observer on the Moon.
        times: Consecutive sample times on the step grid (one chunk, see ``split_chunks``).
        step_minutes: Step, whole minutes.

    Returns:
        Rows aligned with ``times``.

    Raises:
        HorizonsError: On HTTP failure, a Horizons error message or missing samples.
    """
    # Horizons needs STOP > START, so a single-sample chunk asks for one extra step.
    stop = times[-1] if len(times) > 1 else times[0] + timedelta(minutes=step_minutes)
    params = build_params(target, location, times[0], stop, step_minutes)
    log.info("Horizons request target=%s %s..%s (%d rows)", target, times[0], stop, len(times))
    try:
        resp = client.get(HORIZONS_URL, params=params)
        resp.raise_for_status()
        result = resp.json()["result"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise HorizonsError(f"Horizons request for target {target} failed: {exc}") from exc
    rows = parse_result(result)
    index = {t: i for i, t in enumerate(rows.times_utc)}
    missing = [t for t in times if t not in index]
    if missing:
        raise HorizonsError(
            f"Horizons reply for target {target} lacks {len(missing)} samples, first {missing[0]}"
        )
    pick = [index[t] for t in times]
    return AzElRows(
        list(times), [rows.azimuth_deg[i] for i in pick], [rows.elevation_deg[i] for i in pick]
    )


def _to_utc(t: datetime) -> datetime:
    """Convert an aware datetime to UTC, dropping sub-second precision."""
    return t.astimezone(UTC).replace(microsecond=0)


def _fmt(t: datetime) -> str:
    """Format a UTC datetime the way Horizons expects in START_TIME/STOP_TIME."""
    return t.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _parse_time(text: str) -> datetime:
    """Parse a Horizons calendar time like '2026-Dec-01 00:10[:00]' (UTC), locale-independent."""
    date, clock = text.split()
    year, month, day = date.split("-")
    hh, mm, *rest = clock.split(":")
    ss = int(float(rest[0])) if rest else 0
    return datetime(int(year), _MONTHS[month], int(day), int(hh), int(mm), ss, tzinfo=UTC)
