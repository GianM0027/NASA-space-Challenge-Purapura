# ABOUTME: Tests of the horizon mask cache (TER-5): reuse in memory and on disk, keys, bad entries
# ABOUTME: Counts real ray-casting calls by wrapping segmented_horizon_profile in the provider

from pathlib import Path

import numpy as np
import pytest

from lunarnav.contracts import GeoPoint
from lunarnav.terrain import provider as provider_module
from lunarnav.terrain.cache import HorizonCache
from lunarnav.terrain.dem import CylindricalDem
from lunarnav.terrain.provider import LolaTerrainProvider

PPD = 8
SITE = GeoPoint(lat_deg=10.0, lon_deg=20.0)


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Count how many masks are really ray-cast."""
    counter: list[int] = []
    real = provider_module.segmented_horizon_profile

    def counting(*args, **kwargs):
        counter.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(provider_module, "segmented_horizon_profile", counting)
    return counter


def bumpy_global() -> CylindricalDem:
    rng = np.random.default_rng(0)
    grid = rng.uniform(0.0, 2000.0, size=(180 * PPD, 360 * PPD)).astype(np.float32)
    return CylindricalDem("synthetic bumpy", grid, 1.0, PPD)


def test_second_request_is_served_from_memory(calls: list[int]) -> None:
    provider = LolaTerrainProvider(bumpy_global())
    first = provider.horizon_mask(SITE)
    second = provider.horizon_mask(SITE)
    assert len(calls) == 1
    assert second == first


def test_disk_cache_survives_a_new_provider(calls: list[int], tmp_path: Path) -> None:
    dem = bumpy_global()
    first = LolaTerrainProvider(dem, cache=HorizonCache(tmp_path)).horizon_mask(SITE)
    restarted = LolaTerrainProvider(dem, cache=HorizonCache(tmp_path))
    second = restarted.horizon_mask(SITE)
    assert len(calls) == 1
    assert second.horizon_elevation_deg == first.horizon_elevation_deg
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_inputs_that_change_the_mask_change_the_key(calls: list[int]) -> None:
    dem = bumpy_global()
    cache = HorizonCache()
    LolaTerrainProvider(dem, cache=cache).horizon_mask(SITE)
    LolaTerrainProvider(dem, cache=cache, observer_height_above_ground_m=2.0).horizon_mask(SITE)
    LolaTerrainProvider(dem, cache=cache, max_distance_m=50_000.0).horizon_mask(SITE)
    LolaTerrainProvider(dem, cache=cache).horizon_mask(GeoPoint(lat_deg=10.0, lon_deg=20.5))
    assert len(calls) == 4


def test_cached_mask_reports_the_requested_location(calls: list[int]) -> None:
    provider = LolaTerrainProvider(bumpy_global())
    surface = provider.horizon_mask(SITE)
    # Same observer, now given explicitly: served from the cache, location echoes the request.
    explicit = provider.horizon_mask(
        SITE.model_copy(update={"height_m": surface.location.height_m})
    )
    assert len(calls) == 1
    assert explicit.location.height_m == surface.location.height_m


def test_unreadable_disk_entry_is_recomputed(calls: list[int], tmp_path: Path) -> None:
    dem = bumpy_global()
    LolaTerrainProvider(dem, cache=HorizonCache(tmp_path)).horizon_mask(SITE)
    (entry,) = tmp_path.glob("*.json")
    entry.write_text("{not json", encoding="utf-8")
    mask = LolaTerrainProvider(dem, cache=HorizonCache(tmp_path)).horizon_mask(SITE)
    assert len(calls) == 2
    assert len(mask.azimuth_deg) == 360


def test_memory_is_bounded() -> None:
    cache = HorizonCache(max_memory_entries=2)
    provider = LolaTerrainProvider(bumpy_global(), cache=cache)
    for lon in (0.0, 1.0, 2.0):
        provider.horizon_mask(GeoPoint(lat_deg=0.0, lon_deg=lon))
    assert len(cache._memory) == 2
