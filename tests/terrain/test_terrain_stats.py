# ABOUTME: Provider tests of the D32 terrain statistics: landing disk, full disk, reachable share
# ABOUTME: A synthetic crater-like ring (flat floor, 30 deg wall) where every answer is known

import numpy as np
import pytest

from lunarnav.contracts import GeoPoint, OperationsArea, TerrainStats
from lunarnav.terrain.dem import CylindricalDem, SouthPolarStereographicDem
from lunarnav.terrain.provider import LolaTerrainProvider

SITE = GeoPoint(lat_deg=-89.99, lon_deg=0.0)  # ~1.1 km from the pole
WALL_IN, WALL_OUT = 1000.0, 1200.0  # a 30 deg wall between these distances from the site
TAN30 = np.tan(np.radians(30.0))


def ring_provider() -> LolaTerrainProvider:
    n, res = 400, 20.0  # 4 km half width around the pole
    dem = SouthPolarStereographicDem("synthetic ring", np.zeros((n, n)), 1.0, res)
    x0, y0 = dem.xy_m(np.array(SITE.lat_deg), np.array(SITE.lon_deg))
    axis = (np.arange(n) - (n / 2 - 0.5)) * res
    x, y = np.meshgrid(axis, axis)
    r = np.hypot(x - float(x0), y - float(y0))
    dem.heights = np.clip(r - WALL_IN, 0.0, WALL_OUT - WALL_IN) * TAN30
    flat = CylindricalDem("global", np.zeros((180 * 8, 360 * 8), dtype=np.float32), 1.0, 8)
    return LolaTerrainProvider(flat, [dem])


def test_landing_disk_inside_the_floor_is_flat_while_the_full_disk_sees_the_wall() -> None:
    area = OperationsArea(landing_precision_m=500.0, operating_range_m=2000.0)
    stats = ring_provider().terrain_stats(SITE, area)
    TerrainStats.model_validate(stats.model_dump())
    assert stats.landing_radius_m == 500.0 and stats.radius_m == 2500.0
    assert stats.landing_slope_max_deg == pytest.approx(0.0, abs=1e-6)
    assert stats.slope_max_deg == pytest.approx(30.0, abs=0.5)
    assert stats.traverse_slope_limit_deg == 20.0  # contract default, echoed


def test_wall_steeper_than_the_limit_keeps_rovers_on_the_floor() -> None:
    blocked = ring_provider().terrain_stats(
        SITE, OperationsArea(operating_range_m=2000.0, traverse_slope_limit_deg=20.0)
    )
    # The floor (radius ~1 km) is about a quarter of the 2 km disk; the wall cells are lost too.
    floor_share = (WALL_IN / 2000.0) ** 2
    assert blocked.reachable_fraction == pytest.approx(floor_share, abs=0.03)
    allowed = ring_provider().terrain_stats(
        SITE, OperationsArea(operating_range_m=2000.0, traverse_slope_limit_deg=35.0)
    )
    assert allowed.reachable_fraction == pytest.approx(1.0)


def test_no_operating_range_means_no_reachable_share() -> None:
    stats = ring_provider().terrain_stats(SITE, OperationsArea(landing_precision_m=100.0))
    assert stats.reachable_fraction is None


def test_large_areas_use_wider_cells_but_keep_the_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    area = OperationsArea(landing_precision_m=100.0, operating_range_m=2000.0)
    fine = ring_provider().terrain_stats(SITE, area)
    from lunarnav.terrain import provider as provider_module

    monkeypatch.setattr(provider_module, "MAX_GRID_RADIUS_CELLS", 40)  # 2.1 km disk -> 52.5 m cells
    coarse = ring_provider().terrain_stats(SITE, area)
    assert "sampled every 52 m" in coarse.dem_source
    assert coarse.landing_slope_max_deg == fine.landing_slope_max_deg  # landing disk stays fine
    assert coarse.reachable_fraction == pytest.approx(fine.reachable_fraction, abs=0.05)
