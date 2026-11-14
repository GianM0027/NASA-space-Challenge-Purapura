# ABOUTME: EPH-3 warm-up: fills data/cache/ephemeris/ for every catalog site and the globe origin
# ABOUTME: Run once with network before a demo; afterwards those windows are served offline

"""Fill the ephemeris disk cache so the demo works offline (spec EPH-3).

Fetches, one Horizons request at a time:

* every catalog site over the window at ``--step`` minutes (default 10);
* the globe's reference point (lat 0, lon 0, used by ``GET /api/sky``) at ``--globe-step``
  minutes (default 1), so any whole-minute date in the window lights the globe instantly.

A cached window also serves shorter windows inside it and steps that are multiples of the cached
step on the same grid (see ``lunarnav.ephemeris.cache``), so align requests to the warm-up start.

Usage (from the repo root)::

    uv run python scripts/ephemeris_warm_cache.py --start 2026-12-01 --days 60
    uv run python scripts/ephemeris_warm_cache.py --sites apollo-11 im-2 --no-globe
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import UTC, datetime, timedelta

from lunarnav.catalog import JsonSiteCatalog
from lunarnav.contracts import GeoPoint, TimeWindow
from lunarnav.ephemeris import HorizonsEphemerisProvider

log = logging.getLogger("ephemeris_warm_cache")

GLOBE_ORIGIN = GeoPoint(lat_deg=0.0, lon_deg=0.0)  # reference point of lunarnav.api.sky


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line options."""
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--start", default=today, help="window start, UTC date or ISO time (default today)"
    )
    p.add_argument("--days", type=float, default=60.0, help="window length, days (default 60)")
    p.add_argument("--step", type=int, default=10, help="site sampling step, minutes (default 10)")
    p.add_argument("--globe-step", type=int, default=1, help="globe step, minutes (default 1)")
    p.add_argument("--no-globe", action="store_true", help="skip the globe reference point")
    p.add_argument("--sites", nargs="*", help="only these catalog ids (default: all sites)")
    return p.parse_args(argv)


def window(start: datetime, days: float, step: int) -> TimeWindow:
    """Return the warm-up window ``[start, start + days]`` at ``step`` minutes."""
    return TimeWindow(start_utc=start, end_utc=start + timedelta(days=days), step_minutes=step)


def parse_start(text: str) -> datetime:
    """Parse a UTC date ('2026-12-01') or ISO time; naive values are taken as UTC."""
    t = datetime.fromisoformat(text)
    return t.replace(tzinfo=UTC) if t.tzinfo is None else t.astimezone(UTC)


def main(argv: list[str] | None = None) -> int:
    """Warm the cache; return the number of failed targets (0 = all good)."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per request is too noisy
    args = parse_args(argv)
    start = parse_start(args.start)
    sites = JsonSiteCatalog().list_sites()
    if args.sites:
        wanted = set(args.sites)
        sites = [s for s in sites if s.id in wanted]
        missing = wanted - {s.id for s in sites}
        if missing:
            raise SystemExit(f"unknown site ids: {sorted(missing)}")

    targets = [(s.id, s.location, args.step) for s in sites]
    if not args.no_globe:
        targets.append(("globe-origin", GLOBE_ORIGIN, args.globe_step))

    provider = HorizonsEphemerisProvider()
    failures = 0
    t0 = time.perf_counter()
    for i, (name, location, step) in enumerate(targets, 1):
        w = window(start, args.days, step)
        t = time.perf_counter()
        try:
            provider.sun_earth(location, w)
        except Exception as exc:  # keep going: one bad target must not stop the warm-up
            failures += 1
            log.error("[%d/%d] %s FAILED: %s", i, len(targets), name, exc)
            continue
        log.info("[%d/%d] %s ok (%.1f s)", i, len(targets), name, time.perf_counter() - t)
    log.info(
        "done: %d targets, %d failed, %.0f s, window %s + %g days",
        len(targets),
        failures,
        time.perf_counter() - t0,
        start.isoformat(),
        args.days,
    )
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
