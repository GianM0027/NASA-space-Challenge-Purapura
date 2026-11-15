# ABOUTME: TER-5 warm-up: precomputes horizon masks of every catalog site into data/cache/terrain/
# ABOUTME: Run once after downloading the DEMs; afterwards site selections are served from the cache

"""Fill the horizon mask cache for all catalog sites, so no selection waits during a demo.

A horizon mask depends only on the site, the observer height above the ground and the DEMs
(TER-5), so it can be computed ahead of time. By default each site is warmed at the observer
heights of decision D30: 2 m (default, rovers and small landers) and 10 m (large crewed landers).
Already cached masks are skipped quickly; a failing site is reported and the run continues.

Usage (from the repo root, after ``scripts/terrain_download_dem.py``)::

    uv run python scripts/terrain_warm_cache.py
    uv run python scripts/terrain_warm_cache.py --heights 2 --sites apollo-11 im-2
"""

from __future__ import annotations

import argparse
import logging
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from lunarnav.catalog import build_catalog
from lunarnav.contracts import OperationsArea, Site, TerrainProvider
from lunarnav.terrain.provider import DEFAULT_CACHE_DIR, LolaTerrainProvider

log = logging.getLogger("terrain_warm_cache")

# Decision D30 (observer height): 2 m default (Glaser et al. 2014), 10 m for large crewed landers.
DEFAULT_HEIGHTS_M = (2.0, 10.0)


@dataclass(frozen=True)
class WarmReport:
    """Outcome of a warm-up run.

    Attributes:
        masks: Masks requested (sites x heights, failures excluded).
        failures: Site ids whose computation raised.
        seconds: Wall-clock duration of the run.
    """

    masks: int
    failures: list[str]
    seconds: float


def warm_up(
    provider: TerrainProvider, sites: Iterable[Site], heights_m: Sequence[float]
) -> WarmReport:
    """Request the horizon mask of every site at every observer height (filling the cache).

    Args:
        provider: Terrain provider whose cache gets filled.
        sites: Sites to warm.
        heights_m: Observer heights above the ground, meters.

    Returns:
        The report; failing sites are logged and listed, never raised.
    """
    start = time.perf_counter()
    masks, failures = 0, []
    for site in sites:
        try:
            for h in heights_m:
                provider.horizon_mask(
                    site.location, OperationsArea(observer_height_above_ground_m=h)
                )
                masks += 1
        except Exception as exc:  # one bad site must not stop the warm-up
            log.error("  %s failed: %s", site.id, exc)
            failures.append(site.id)
            continue
        log.info("  %s ready", site.id)
    return WarmReport(masks, failures, time.perf_counter() - start)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line options."""
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--heights",
        nargs="+",
        type=float,
        default=list(DEFAULT_HEIGHTS_M),
        help="observer heights above ground, meters (default: 2 10, decision D30)",
    )
    p.add_argument("--sites", nargs="*", help="only these catalog ids (default: all sites)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Warm the cache; return the number of failed sites (0 means success)."""
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sites = build_catalog().list_sites()
    if args.sites:
        unknown = set(args.sites) - {s.id for s in sites}
        if unknown:
            log.error("unknown site ids: %s", sorted(unknown))
            return len(unknown)
        sites = [s for s in sites if s.id in args.sites]
    before = len(list(DEFAULT_CACHE_DIR.glob("*.json"))) if DEFAULT_CACHE_DIR.exists() else 0
    provider = LolaTerrainProvider.from_raw_dir()
    log.info("warming %d sites at heights %s m", len(sites), args.heights)
    report = warm_up(provider, sites, args.heights)
    after = len(list(DEFAULT_CACHE_DIR.glob("*.json")))
    log.info(
        "done: %d masks (%d newly computed) in %.1f s; %d failures %s",
        report.masks,
        after - before,
        report.seconds,
        len(report.failures),
        report.failures or "",
    )
    return len(report.failures)


if __name__ == "__main__":
    raise SystemExit(main())
