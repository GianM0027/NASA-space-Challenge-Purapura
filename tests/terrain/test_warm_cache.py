# ABOUTME: Tests of the terrain warm-up script (TER-5): fills the disk cache, skips cached masks
# ABOUTME: Synthetic DEM and a temporary cache folder; no real DEMs needed

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

from lunarnav.contracts import GeoPoint, Origin, Site
from lunarnav.terrain import provider as provider_module
from lunarnav.terrain.cache import HorizonCache
from lunarnav.terrain.dem import CylindricalDem
from lunarnav.terrain.provider import LolaTerrainProvider

SCRIPT = Path(__file__).parents[2] / "scripts" / "terrain_warm_cache.py"


def load_script():
    spec = importlib.util.spec_from_file_location("terrain_warm_cache", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(module)
    return module


def site(site_id: str, lat: float, lon: float) -> Site:
    return Site(
        id=site_id,
        name=site_id,
        location=GeoPoint(lat_deg=lat, lon_deg=lon),
        origin=Origin.USER,
        status="custom",
    )


def synthetic_provider(cache_dir: Path) -> LolaTerrainProvider:
    rng = np.random.default_rng(0)
    grid = rng.uniform(0.0, 2000.0, size=(180 * 8, 360 * 8)).astype(np.float32)
    return LolaTerrainProvider(
        CylindricalDem("synthetic", grid, 1.0, 8), cache=HorizonCache(cache_dir)
    )


def test_warm_up_writes_one_entry_per_site_and_height(tmp_path: Path) -> None:
    script = load_script()
    sites = [site("a", 0.0, 0.0), site("b", 10.0, 20.0)]
    report = script.warm_up(synthetic_provider(tmp_path), sites, [2.0, 10.0])
    assert report.masks == 4 and report.failures == []
    assert len(list(tmp_path.glob("*.json"))) == 4


def test_second_run_reads_the_cache_instead_of_ray_casting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = load_script()
    sites = [site("a", 0.0, 0.0)]
    script.warm_up(synthetic_provider(tmp_path), sites, [2.0])
    calls: list[int] = []
    real = provider_module.segmented_horizon_profile
    monkeypatch.setattr(
        provider_module,
        "segmented_horizon_profile",
        lambda *a, **k: calls.append(1) or real(*a, **k),
    )
    script.warm_up(synthetic_provider(tmp_path), sites, [2.0])  # fresh provider, same folder
    assert calls == []


def test_a_failing_site_is_reported_and_the_run_continues(tmp_path: Path) -> None:
    script = load_script()

    class Flaky:
        def horizon_mask(self, location, area):
            if location.lat_deg == 5.0:
                raise RuntimeError("DEM read error")
            return synthetic_provider(tmp_path).horizon_mask(location, area)

    report = script.warm_up(Flaky(), [site("bad", 5.0, 0.0), site("ok", 0.0, 0.0)], [2.0])
    assert report.failures == ["bad"] and report.masks == 1
