# ABOUTME: Known-answer tests of D36: 100 m baseline landing slopes, 99th percentile slope maxima
# ABOUTME: Exact plane fits, a periodic roughness with a closed-form answer, an isolated spike

import numpy as np
import pytest

from lunarnav.contracts import GeoPoint, OperationsArea
from lunarnav.terrain.dem import CylindricalDem, SouthPolarStereographicDem
from lunarnav.terrain.provider import LolaTerrainProvider
from lunarnav.terrain.slope import (
    LANDING_BASELINE_M,
    SlopeGrid,
    _fit_offsets,
    _plane_fit_gradient,
    slope_grid,
)

STEP = 20.0


def test_fit_neighbourhood_is_the_cells_within_50_m() -> None:
    # On a 20 m grid: rows 0 and +-1 take columns -2..2, rows +-2 take columns -1..1 (21 cells);
    # (2, 2) is 56.6 m away and stays out.
    offsets = _fit_offsets(STEP, LANDING_BASELINE_M / 2)
    assert len(offsets) == 21 and (2, 2) not in offsets and (2, 1) in offsets
    assert _fit_offsets(80.0, LANDING_BASELINE_M / 2) == []  # 80 m cells: nothing within 50 m


def test_plane_fit_recovers_a_plane_exactly() -> None:
    cols, rows = np.meshgrid(np.arange(30), np.arange(30))
    heights = 0.3 * cols * STEP - 0.1 * rows * STEP  # dh/deast 0.3, dh/dnorth -0.1
    east, north = _plane_fit_gradient(heights, _fit_offsets(STEP, 50.0), STEP)
    assert np.allclose(east[5:-5, 5:-5], 0.3) and np.allclose(north[5:-5, 5:-5], -0.1)


def test_periodic_roughness_shrinks_by_the_closed_form_factor() -> None:
    # h = A sin(pi j / 2) along columns (period 4 cells). Central differences give A cos(...)/s;
    # the plane fit gives sum(dx z)/sum(dx^2) = 10 A s cos / (34 s^2): exactly 10/34 of it.
    amplitude = 5.0
    cols = np.tile(np.arange(40), (40, 1))
    heights = amplitude * np.sin(np.pi * cols / 2)
    fitted, _ = _plane_fit_gradient(heights, _fit_offsets(STEP, 50.0), STEP)
    pixel = np.gradient(heights, STEP, axis=1)
    inner = (slice(5, -5), slice(5, -5))
    assert np.abs(pixel[inner]).max() == pytest.approx(amplitude / STEP)
    assert np.abs(fitted[inner]).max() == pytest.approx(10 / 34 * amplitude / STEP)


def test_robust_maximum_ignores_one_spike_in_a_large_disk() -> None:
    k = 15  # 31 x 31 grid, ~700 cells in the 300 m disk
    axis = np.arange(-k, k + 1) * STEP
    east, north = np.meshgrid(axis, axis)
    slope = np.full(east.shape, 5.0)
    slope[k + 3, k + 4] = 60.0  # one bad pixel
    grid = SlopeGrid(east, north, np.zeros_like(east), slope, STEP, k, 2 * STEP)
    stats = grid.disk_stats(300.0)
    assert stats.slope_max_deg == pytest.approx(5.0)  # 99th percentile, not the spike
    assert stats.slope_mean_deg > 5.0


def test_landing_slope_on_a_polar_plane_uses_the_100_m_baseline() -> None:
    n, res = 400, 20.0
    x = (np.arange(n) - (n / 2 - 0.5)) * res
    dem = SouthPolarStereographicDem(
        "synthetic polar", np.tile(np.tan(np.radians(12.0)) * x, (n, 1)), 1.0, res
    )
    grid = slope_grid(dem, -89.9, 45.0, 100.0, baseline_m=LANDING_BASELINE_M)
    assert grid.baseline_m == 100.0
    flat = CylindricalDem("global", np.zeros((180 * 8, 360 * 8), dtype=np.float32), 1.0, 8)
    stats = LolaTerrainProvider(flat, [dem]).terrain_stats(
        GeoPoint(lat_deg=-89.9, lon_deg=45.0), OperationsArea(landing_precision_m=100.0)
    )
    assert stats.landing_slope_mean_deg == pytest.approx(12.0, abs=0.05)
    assert stats.landing_slope_max_deg == pytest.approx(12.0, abs=0.05)


def test_provider_landing_slopes_smooth_roughness_that_pixel_slopes_see() -> None:
    # Pure roughness: h = 5 m sin(pi col / 2), period 4 cells of 20 m. At lon 0 near the south pole
    # the local east axis follows the grid columns. With no operating range the full disk equals
    # the landing disk, so the full-disk (pixel baseline) slopes are the reference.
    n, res = 400, 20.0
    cols = np.tile(np.arange(n), (n, 1))
    dem = SouthPolarStereographicDem("rough", 5.0 * np.sin(np.pi * cols / 2), 1.0, res)
    flat = CylindricalDem("global", np.zeros((180 * 8, 360 * 8), dtype=np.float32), 1.0, 8)
    stats = LolaTerrainProvider(flat, [dem]).terrain_stats(
        GeoPoint(lat_deg=-89.9, lon_deg=0.0), OperationsArea(landing_precision_m=200.0)
    )
    assert stats.radius_m == stats.landing_radius_m == 200.0
    assert stats.landing_slope_mean_deg < 0.5 * stats.slope_mean_deg
