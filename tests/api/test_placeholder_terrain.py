# ABOUTME: Smoke tests of the placeholder terrain provider: the operations area drives its output
# ABOUTME: Owner: Gian; radii and slope limit are echoed, no reachable share without a range

from lunarnav.api.services import ExampleTerrainProvider
from lunarnav.contracts import GeoPoint, OperationsArea

SITE = GeoPoint(lat_deg=-89.5, lon_deg=0.0)


def test_radii_and_slope_limit_come_from_the_area() -> None:
    area = OperationsArea(
        landing_precision_m=100.0, operating_range_m=2_000.0, traverse_slope_limit_deg=15.0
    )
    stats = ExampleTerrainProvider().terrain_stats(SITE, area)
    assert stats.radius_m == 2_100.0
    assert stats.landing_radius_m == 100.0
    assert stats.traverse_slope_limit_deg == 15.0
    assert stats.reachable_fraction is not None


def test_no_reachable_fraction_without_an_operating_range() -> None:
    stats = ExampleTerrainProvider().terrain_stats(SITE, OperationsArea(landing_precision_m=50.0))
    assert stats.reachable_fraction is None
