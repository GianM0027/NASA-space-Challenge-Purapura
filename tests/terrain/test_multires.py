# ABOUTME: Known-answer tests of multi-resolution rays (TER-4): fine DEM near, coarse DEM far
# ABOUTME: Synthetic polar grids where each relief exists in one DEM only, so both must be read

import numpy as np
import pytest

from lunarnav.contracts import GeoPoint
from lunarnav.terrain.dem import (
    CylindricalDem,
    SouthPolarStereographicDem,
    load_lola_south_polar,
)
from lunarnav.terrain.horizon import elevation_angle_deg
from lunarnav.terrain.provider import DEFAULT_RAW_DIR, LolaTerrainProvider

SITE = GeoPoint(lat_deg=-89.99, lon_deg=0.0)  # ~1.1 km from the pole


def flat_global() -> CylindricalDem:
    return CylindricalDem("global", np.zeros((180 * 8, 360 * 8), dtype=np.float32), 1.0, 8)


def polar(name: str, n: int, res: float, height_of_r) -> SouthPolarStereographicDem:
    """Polar grid whose height depends on the projected distance r from SITE."""
    dem = SouthPolarStereographicDem(name, np.zeros((n, n)), 1.0, res)
    x0, y0 = dem.xy_m(np.array(SITE.lat_deg), np.array(SITE.lon_deg))
    axis = (np.arange(n) - (n / 2 - 0.5)) * res
    x, y = np.meshgrid(axis, axis)  # columns: x, rows: y (same layout as Dem.pixel)
    dem.heights = height_of_r(np.hypot(x - float(x0), y - float(y0)))
    return dem


def fine_dem(height_of_r) -> SouthPolarStereographicDem:
    return polar("fine 20 m", 1200, 20.0, height_of_r)  # 12 km half width


def coarse_dem(height_of_r) -> SouthPolarStereographicDem:
    return polar("coarse 100 m", 1000, 100.0, height_of_r)  # 50 km half width


def provider(fine, coarse) -> LolaTerrainProvider:
    return LolaTerrainProvider(flat_global(), [coarse, fine], max_distance_m=40_000.0)


def flat(r):
    return np.zeros_like(r)


def test_near_relief_known_only_to_the_fine_dem_is_seen() -> None:
    # A 100 m wall, 200 m thick, 2 km away in every direction: the coarse DEM never sees it.
    wall = fine_dem(lambda r: np.where((r >= 2000.0) & (r <= 2200.0), 100.0, 0.0))
    mask = provider(wall, coarse_dem(flat)).horizon_mask(SITE)
    # The rasterized wall edge is blurred by up to two 20 m pixels: seen between 2000 and 2040 m
    # (2.83 to 2.77 deg). Read on the coarse DEM alone the horizon would be ~0 deg.
    upper = elevation_angle_deg(2000.0, 100.0, 0.0)
    lower = elevation_angle_deg(2040.0, 100.0, 0.0)
    elevations = np.array(mask.horizon_elevation_deg)
    assert np.all((elevations >= lower - 0.005) & (elevations <= upper + 0.005))
    assert mask.dem_resolution_m == 20.0
    assert "fine 20 m" in mask.dem_source and "coarse 100 m" in mask.dem_source


def test_far_relief_beyond_the_fine_dem_is_seen() -> None:
    # A 2 km plateau from 30 km outward exists only in the coarse DEM (the fine one ends at 12 km).
    plateau = coarse_dem(lambda r: np.where(r >= 30_000.0, 2000.0, 0.0))
    mask = provider(fine_dem(flat), plateau).horizon_mask(SITE)
    expected = elevation_angle_deg(30_000.0, 2000.0, 0.0)  # ~3.67 deg
    assert np.allclose(mask.horizon_elevation_deg, expected, atol=0.05)


def test_observer_stands_on_the_fine_dem() -> None:
    fine = fine_dem(lambda r: np.full_like(r, 12.0))
    coarse = coarse_dem(lambda r: np.full_like(r, 30.0))
    mask = provider(fine, coarse).horizon_mask(SITE)
    assert mask.location.height_m == pytest.approx(12.0)


def test_without_a_finer_dem_a_single_resolution_is_used() -> None:
    p = LolaTerrainProvider(flat_global(), [coarse_dem(flat)], max_distance_m=40_000.0)
    mask = p.horizon_mask(SITE)
    assert mask.dem_resolution_m == 100.0 and " beyond" not in mask.dem_source


def test_slopes_use_the_finest_dem() -> None:
    fine, coarse = fine_dem(flat), coarse_dem(flat)
    stats = provider(fine, coarse).terrain_stats(SITE, 500.0)
    assert stats.dem_resolution_m == 20.0


# --- Real LOLA data (run with `uv run pytest -m slow`) ------------------------------------------

RAW = DEFAULT_RAW_DIR
needs_fine_dem = pytest.mark.skipif(
    not (RAW / "ldem_80s_80m.img").exists() or not (RAW / "ldem_85s_20m.img").exists(),
    reason="south polar LOLA DEMs missing: run scripts/terrain_download_dem.py",
)


@pytest.mark.slow
@needs_fine_dem
def test_real_20m_and_80m_polar_dems_agree_and_share_orientation() -> None:
    # Check of TER-4: median difference 0.7 m and 95th percentile 3 m when first measured; a
    # mirrored projection gives ~1 km. Thresholds leave room for interpolation differences.
    coarse = load_lola_south_polar(RAW / "ldem_80s_80m.img", 7600, 80.0)
    fine = load_lola_south_polar(RAW / "ldem_85s_20m.img", 15168, 20.0)
    rng = np.random.default_rng(1)
    lat, lon = rng.uniform(-89.9, -85.2, 3000), rng.uniform(-180.0, 180.0, 3000)
    diff = np.abs(fine.height_m(lat, lon) - coarse.height_m(lat, lon))
    assert np.median(diff) < 5.0
    assert np.percentile(diff, 95) < 20.0


@pytest.mark.slow
@needs_fine_dem
def test_real_provider_uses_the_20m_dem_near_polar_sites() -> None:
    provider = LolaTerrainProvider.from_raw_dir(cache_dir=None)
    mask = provider.horizon_mask(GeoPoint(lat_deg=-85.98, lon_deg=-1.67))  # Malapert area
    assert mask.dem_resolution_m == 20.0
    assert "LDEM_85S_20M" in mask.dem_source and "LDEM_80S_80M" in mask.dem_source
