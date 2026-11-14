# ABOUTME: Known-answer tests of terrain slope statistics over a disk (TER-2)
# ABOUTME: Synthetic inclined planes on the global and polar grids; real-LOLA checks marked slow

from pathlib import Path

import numpy as np
import pytest

from lunarnav.contracts import GeoPoint, TerrainStats
from lunarnav.terrain.dem import MOON_RADIUS_M, CylindricalDem, SouthPolarStereographicDem
from lunarnav.terrain.provider import DEFAULT_RAW_DIR, LolaTerrainProvider
from lunarnav.terrain.slope import slope_stats

PPD = 8  # synthetic global grid: 1/8 degree pixels, ~3.8 km


def global_grid(func) -> CylindricalDem:
    """Global grid whose height at each pixel center is func(lat_deg, lon_deg)."""
    lat = 90.0 - (np.arange(180 * PPD) + 0.5) / PPD
    lon = (np.arange(360 * PPD) + 0.5) / PPD
    lon_grid, lat_grid = np.meshgrid(lon, lat)
    return CylindricalDem("synthetic", func(lat_grid, lon_grid), 1.0, PPD)


def test_plane_rising_northward_has_its_slope_everywhere() -> None:
    # Height grows by tan(10 deg) meters per meter of northward arc: a 10 degree slope.
    tilt = np.tan(np.radians(10.0))
    dem = global_grid(lambda lat, lon: tilt * MOON_RADIUS_M * np.radians(lat))
    stats = slope_stats(dem, 0.0, 30.0, 20_000.0)
    assert stats.slope_mean_deg == pytest.approx(10.0, abs=0.05)
    assert stats.slope_max_deg == pytest.approx(10.0, abs=0.05)
    assert stats.elevation_m == pytest.approx(0.0, abs=1.0)


def test_plane_rising_eastward_at_the_equator() -> None:
    # Along the equator one degree of longitude is one degree of arc: tan(20 deg) per meter east.
    tilt = np.tan(np.radians(20.0))
    dem = global_grid(lambda lat, lon: tilt * MOON_RADIUS_M * np.radians(lon - 90.0))
    stats = slope_stats(dem, 0.0, 90.0, 10_000.0)
    assert stats.slope_mean_deg == pytest.approx(20.0, abs=0.1)
    assert stats.elevation_m == pytest.approx(0.0, abs=1.0)


def test_flat_terrain_has_zero_slope_and_its_height() -> None:
    dem = global_grid(lambda lat, lon: np.full_like(lat, 1500.0))
    stats = slope_stats(dem, -45.0, -120.0, 5_000.0)
    assert stats.slope_max_deg == pytest.approx(0.0, abs=1e-9)
    assert stats.elevation_m == pytest.approx(1500.0)


def test_zero_radius_uses_the_center_point_only() -> None:
    tilt = np.tan(np.radians(10.0))
    dem = global_grid(lambda lat, lon: tilt * MOON_RADIUS_M * np.radians(lat))
    stats = slope_stats(dem, 0.0, 30.0, 0.0)
    assert stats.slope_mean_deg == stats.slope_max_deg == pytest.approx(10.0, abs=0.05)


def test_negative_radius_is_rejected() -> None:
    dem = global_grid(lambda lat, lon: np.zeros_like(lat))
    with pytest.raises(ValueError, match="must be >= 0"):
        slope_stats(dem, 0.0, 0.0, -1.0)


def polar_plane(slope_deg: float) -> SouthPolarStereographicDem:
    """100 m polar grid with height = tan(slope) * x; near the pole the projection scale is ~1."""
    n, res = 400, 100.0
    x = (np.arange(n) - (n / 2 - 0.5)) * res
    heights = np.tile(np.tan(np.radians(slope_deg)) * x, (n, 1))
    return SouthPolarStereographicDem("synthetic polar", heights, 1.0, res)


def test_plane_on_the_polar_grid() -> None:
    # 3 km from the pole the scale is 1 to within 1e-6: 15 degrees whatever the local north.
    stats = slope_stats(polar_plane(15.0), -89.9, 45.0, 2_000.0)
    assert stats.slope_mean_deg == pytest.approx(15.0, abs=0.05)
    assert stats.slope_max_deg == pytest.approx(15.0, abs=0.05)


def test_provider_handles_a_site_exactly_on_the_pole() -> None:
    # At -90 every direction is north; without the pole guard the grid collapses onto one
    # meridian and the plane looks flat.
    provider = LolaTerrainProvider(
        global_grid(lambda lat, lon: np.zeros_like(lat)), [polar_plane(15.0)]
    )
    stats = provider.terrain_stats(GeoPoint(lat_deg=-90.0, lon_deg=0.0), 2_000.0)
    assert stats.dem_source.startswith("synthetic polar")
    assert stats.slope_mean_deg == pytest.approx(15.0, abs=0.05)


def test_provider_returns_valid_terrain_stats_even_at_the_pole() -> None:
    dem = global_grid(lambda lat, lon: np.full_like(lat, 100.0))
    provider = LolaTerrainProvider(dem)
    for lat in (0.0, -90.0, 90.0):
        stats = provider.terrain_stats(GeoPoint(lat_deg=lat, lon_deg=0.0), 3_000.0)
        TerrainStats.model_validate(stats.model_dump())
        assert stats.slope_max_deg == pytest.approx(0.0, abs=1e-6)
        assert stats.elevation_m == pytest.approx(100.0)


# --- Real LOLA data (run with `uv run pytest -m slow`) ------------------------------------------

needs_dems = pytest.mark.skipif(
    not (Path(DEFAULT_RAW_DIR) / "ldem_64.img").exists()
    or not (Path(DEFAULT_RAW_DIR) / "ldem_80s_80m.img").exists(),
    reason="LOLA DEMs missing: run scripts/terrain_download_dem.py",
)


@pytest.mark.slow
@needs_dems
def test_real_slopes_mare_is_gentle_and_shackleton_walls_are_steep() -> None:
    provider = LolaTerrainProvider.from_raw_dir()
    mare = provider.terrain_stats(GeoPoint(lat_deg=0.674, lon_deg=23.473), 5_000.0)
    # Shackleton (approx. 89.67 S, 129.78 E, radius ~10.5 km): inner walls of roughly 30 degrees.
    crater = provider.terrain_stats(GeoPoint(lat_deg=-89.67, lon_deg=129.78), 10_500.0)
    assert mare.slope_mean_deg < 5.0
    assert crater.dem_resolution_m == 80.0
    assert crater.slope_max_deg > 25.0
    assert crater.slope_mean_deg > mare.slope_mean_deg
