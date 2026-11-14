# ABOUTME: Known-answer tests of the terrain DEM lookup and horizon ray casting (TER-1)
# ABOUTME: Synthetic grids by default; the real-LOLA cross-checks are marked slow

from pathlib import Path

import numpy as np
import pytest

from lunarnav.contracts import GeoPoint, HorizonMask
from lunarnav.terrain.dem import (
    MOON_RADIUS_M,
    CylindricalDem,
    SouthPolarStereographicDem,
)
from lunarnav.terrain.horizon import elevation_angle_deg, horizon_profile
from lunarnav.terrain.provider import DEFAULT_RAW_DIR, LolaTerrainProvider

PPD = 8  # synthetic global grid: 1/8 degree pixels, ~3.8 km


def flat_global(height_m: float = 0.0) -> CylindricalDem:
    grid = np.full((180 * PPD, 360 * PPD), height_m, dtype=np.float32)
    return CylindricalDem("synthetic flat", grid, 1.0, PPD)


# --- DEM lookup -------------------------------------------------------------------------------


def test_bilinear_between_pixel_centers_and_across_the_date_line() -> None:
    grid = np.tile(np.arange(360 * PPD, dtype=np.float64), (180 * PPD, 1))
    dem = CylindricalDem("column index", grid, 1.0, PPD)
    # col = lon * ppd - 0.5, so lon = 11/8 deg is col 10.5: halfway between values 10 and 11.
    assert dem.height_m(np.array([0.0]), np.array([11 / PPD]))[0] == pytest.approx(10.5)
    # lon = 0 is col -0.5: halfway between the last column (2879) and the first (0).
    assert dem.height_m(np.array([0.0]), np.array([0.0]))[0] == pytest.approx(2879 / 2)


def test_south_polar_grid_puts_east_on_plus_x() -> None:
    # Convention verified against LDEM_64 in check C1: lon 90 E lies right of the pole (larger
    # column), lon 0 lies above it (smaller row). The mirrored convention fails this test.
    dem = SouthPolarStereographicDem("synthetic", np.zeros((100, 100)), 1.0, 1000.0)
    row_e, col_e = dem.pixel(np.array([-89.0]), np.array([90.0]))
    row_0, col_0 = dem.pixel(np.array([-89.0]), np.array([0.0]))
    assert col_e[0] > 49.5 and row_e[0] == pytest.approx(49.5)
    assert row_0[0] < 49.5 and col_0[0] == pytest.approx(49.5)


def test_south_polar_contains() -> None:
    dem = SouthPolarStereographicDem("synthetic", np.zeros((7600, 7600)), 1.0, 80.0)
    assert dem.contains(-89.5, 0.0, 150_000.0)  # 15 km from the pole + 150 km < 304 km
    assert not dem.contains(-80.0, 0.0, 150_000.0)  # 303 km from the pole
    assert not dem.contains(10.0, 0.0, 0.0)


# --- Horizon geometry -------------------------------------------------------------------------


def test_flat_sphere_horizon_is_minus_half_the_first_step_angle() -> None:
    # On a bare sphere atan2(cos t - 1, sin t) = -t/2: the nearest sample is the highest one.
    _, mask = horizon_profile(flat_global(), 0.0, 0.0, 0.0, 150_000.0)
    step_angle_deg = 1.0 / PPD  # one pixel of a 1/8 degree grid
    assert np.allclose(mask, -step_angle_deg / 2, atol=1e-9)


def test_observer_above_flat_sphere_sees_the_geometric_dip() -> None:
    # Classic horizon dip from height H over a sphere: acos(R / (R + H)), ~1.94 deg for 1 km.
    h = 1000.0
    _, mask = horizon_profile(flat_global(), 10.0, 45.0, h, 150_000.0, step_m=50.0)
    dip_deg = np.degrees(np.arccos(MOON_RADIUS_M / (MOON_RADIUS_M + h)))
    assert np.allclose(mask, -dip_deg, atol=0.005)


def test_ridge_of_known_height_and_distance() -> None:
    # A 3 km plateau starts at the row whose center is 2.0625 N (rows 0..703 of the 1/8 grid);
    # bilinear interpolation ramps up over the pixel before it.
    height, edge_lat = 3000.0, 2.0625
    grid = np.zeros((180 * PPD, 360 * PPD), dtype=np.float32)
    grid[: int((90 - edge_lat) * PPD + 0.5)] = height
    dem = CylindricalDem("synthetic ridge", grid, 1.0, PPD)
    az, mask = horizon_profile(dem, 0.0, 0.0, 0.0, 150_000.0, step_m=100.0)
    edge_distance = np.radians(edge_lat) * MOON_RADIUS_M  # ~62.5 km
    expected = elevation_angle_deg(edge_distance, height, 0.0)  # ~2.47 deg
    assert mask[az == 0.0][0] == pytest.approx(expected, abs=0.01)
    # Looking south the plateau is behind the observer: bare-sphere horizon.
    assert mask[az == 180.0][0] == pytest.approx(-np.degrees(100.0 / MOON_RADIUS_M) / 2, abs=1e-6)


def test_max_distance_below_one_step_is_rejected() -> None:
    with pytest.raises(ValueError, match="below the ray step"):
        horizon_profile(flat_global(), 0.0, 0.0, 0.0, 10.0)


# --- Provider ---------------------------------------------------------------------------------


def test_provider_uses_polar_dem_near_the_pole_and_global_elsewhere() -> None:
    polar = SouthPolarStereographicDem("synthetic polar", np.full((400, 400), 7.0), 1.0, 1000.0)
    provider = LolaTerrainProvider(flat_global(), [polar])
    near_pole = provider.horizon_mask(GeoPoint(lat_deg=-89.9, lon_deg=0.0))
    equator = provider.horizon_mask(GeoPoint(lat_deg=0.0, lon_deg=0.0))
    assert near_pole.dem_source.startswith("synthetic polar")
    assert near_pole.location.height_m == pytest.approx(7.0)  # filled from the DEM
    assert equator.dem_source.startswith("synthetic flat")
    for mask in (near_pole, equator):
        HorizonMask.model_validate(mask.model_dump())
        assert len(mask.azimuth_deg) == 360 and mask.azimuth_deg[1] == 1.0


# --- Real LOLA data (run with `uv run pytest -m slow`) ------------------------------------------

needs_dems = pytest.mark.skipif(
    not (Path(DEFAULT_RAW_DIR) / "ldem_64.img").exists()
    or not (Path(DEFAULT_RAW_DIR) / "ldem_80s_80m.img").exists(),
    reason="LOLA DEMs missing: run scripts/terrain_download_dem.py",
)


@pytest.mark.slow
@needs_dems
def test_real_dems_agree_at_the_south_pole() -> None:
    provider = LolaTerrainProvider.from_raw_dir()
    site = GeoPoint(lat_deg=-89.5, lon_deg=0.0)
    polar = provider.horizon_mask(site)
    global_mask = LolaTerrainProvider(provider.global_dem).horizon_mask(site)
    assert polar.dem_resolution_m in (20.0, 80.0)  # 20 m near field when ldem_85s_20m is present
    p, g = np.array(polar.horizon_elevation_deg), np.array(global_mask.horizon_elevation_deg)
    assert abs(p.max() - g.max()) < 0.3
    assert abs(int(p.argmax()) - int(g.argmax())) <= 3  # degrees of azimuth
    assert np.median(np.abs(p - g)) < 0.3


@pytest.mark.slow
@needs_dems
def test_real_dems_place_shackleton_crater_correctly() -> None:
    # Shackleton (approx. 89.67 S, 129.78 E, radius ~10.5 km) is ~4 km deep: the center must lie
    # far below the rim on both grids. A mirrored projection puts the center on the rim.
    provider = LolaTerrainProvider.from_raw_dir()
    lat, lon, radius = -89.67, 129.78, 10_500.0
    from lunarnav.terrain.horizon import destination

    rim_lat, rim_lon = destination(lat, lon, np.arange(0.0, 360.0, 10.0), np.array([radius]))
    for dem in (provider.global_dem, *provider.regional_dems):
        center = dem.height_m(np.array([lat]), np.array([lon]))[0]
        rim = dem.height_m(rim_lat, rim_lon).mean()
        assert center - rim < -3000.0, dem.name


# --- Observer height ---------------------------------------------------------------------------


def test_height_above_ground_lifts_the_observer_over_flat_terrain() -> None:
    # 1 km mast on a bare sphere: the classic dip acos(R / (R + H)) again, ~1.94 deg.
    provider = LolaTerrainProvider(flat_global(), observer_height_above_ground_m=1000.0)
    mask = provider.horizon_mask(GeoPoint(lat_deg=10.0, lon_deg=45.0))
    assert mask.location.height_m == pytest.approx(1000.0)
    dip_deg = np.degrees(np.arccos(MOON_RADIUS_M / (MOON_RADIUS_M + 1000.0)))
    # Default ray step is one 3.8 km pixel, so the tangent point is sampled coarsely.
    assert np.allclose(mask.horizon_elevation_deg, -dip_deg, atol=0.05)


def test_absolute_height_overrides_height_above_ground() -> None:
    provider = LolaTerrainProvider(flat_global(), observer_height_above_ground_m=1000.0)
    mask = provider.horizon_mask(GeoPoint(lat_deg=0.0, lon_deg=0.0, height_m=5.0))
    assert mask.location.height_m == 5.0


def test_observer_below_the_terrain_is_rejected() -> None:
    provider = LolaTerrainProvider(flat_global(height_m=100.0))
    provider.horizon_mask(GeoPoint(lat_deg=0.0, lon_deg=0.0, height_m=99.5))  # within tolerance
    with pytest.raises(ValueError, match="below the terrain"):
        provider.horizon_mask(GeoPoint(lat_deg=0.0, lon_deg=0.0, height_m=50.0))


def test_negative_height_above_ground_is_rejected() -> None:
    with pytest.raises(ValueError, match="must be >= 0"):
        LolaTerrainProvider(flat_global(), observer_height_above_ground_m=-2.0)


@pytest.mark.slow
@needs_dems
def test_app_provider_places_the_observer_2_m_above_the_ground() -> None:
    # Decision D30: the app default is 2 m above the DEM surface (Glaser et al. 2014).
    app = LolaTerrainProvider.from_raw_dir(cache_dir=None)
    surface = LolaTerrainProvider.from_raw_dir(cache_dir=None, observer_height_above_ground_m=0.0)
    site = GeoPoint(lat_deg=0.674, lon_deg=23.473)
    lifted = app.horizon_mask(site).location.height_m
    ground = surface.horizon_mask(site).location.height_m
    assert lifted - ground == pytest.approx(2.0)
