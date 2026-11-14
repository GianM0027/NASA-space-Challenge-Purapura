# ABOUTME: Known-answer tests of the evaluator: visibility vs mask, runs, events (EVA-1, EVA-2)
# ABOUTME: Fakes of the ephemeris and terrain providers return synthetic series and example payloads

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from lunarnav.contracts import (
    EphemerisSeries,
    Evaluation,
    GeoPoint,
    HorizonMask,
    OperationsArea,
    TerrainStats,
    TimeWindow,
)
from lunarnav.evaluation import LunarEvaluator, build_evaluator
from lunarnav.evaluation.visibility import horizon_at, longest_run_h

EXAMPLES = Path(__file__).resolve().parents[2] / "data" / "examples"
T0 = datetime(2027, 1, 1, tzinfo=UTC)
SITE = GeoPoint(lat_deg=-89.5, lon_deg=0.0)


class FakeEphemeris:
    def __init__(self, sun_el, sun_az=None, earth_el=None, earth_az=None, step_min=60):
        n = len(sun_el)
        self.series = dict(
            times_utc=[T0 + timedelta(minutes=step_min * i) for i in range(n)],
            sun_azimuth_deg=sun_az or [180.0] * n,
            sun_elevation_deg=sun_el,
            earth_azimuth_deg=earth_az or [0.0] * n,
            earth_elevation_deg=earth_el or [10.0] * n,
        )

    def sun_earth(self, location: GeoPoint, window: TimeWindow) -> EphemerisSeries:
        return EphemerisSeries(location=location, source="fake", **self.series)


class FakeTerrain:
    def __init__(self, mask_az=None, mask_el=None):
        self.mask_az = mask_az or [float(a) for a in range(360)]
        self.mask_el = mask_el or [0.0] * len(self.mask_az)
        self.radius_asked: float | None = None

    def horizon_mask(self, location: GeoPoint) -> HorizonMask:
        return HorizonMask(
            location=location,
            azimuth_deg=self.mask_az,
            horizon_elevation_deg=self.mask_el,
            dem_source="fake",
            dem_resolution_m=100.0,
            max_distance_m=1000.0,
        )

    def terrain_stats(self, location: GeoPoint, radius_m: float) -> TerrainStats:
        self.radius_asked = radius_m
        return TerrainStats(
            location=location,
            radius_m=radius_m,
            elevation_m=0.0,
            slope_mean_deg=1.0,
            slope_max_deg=2.0,
            dem_source="fake",
            dem_resolution_m=100.0,
        )


def window(n: int, step_min: int = 60) -> TimeWindow:
    return TimeWindow(
        start_utc=T0, end_utc=T0 + timedelta(minutes=step_min * (n - 1)), step_minutes=step_min
    )


def evaluate(ephemeris: FakeEphemeris, terrain: FakeTerrain | None = None, n: int = 6, **kw):
    terrain = terrain or FakeTerrain()
    return LunarEvaluator(ephemeris, terrain).evaluate(SITE, window(n, **kw), OperationsArea())


# --- Building blocks ---------------------------------------------------------------------------


def test_horizon_interpolation_is_linear_and_wraps_at_north() -> None:
    az = np.array([0.0, 90.0, 180.0, 270.0])
    el = np.array([0.0, 10.0, 0.0, 20.0])
    assert horizon_at(az, el, np.array([45.0]))[0] == pytest.approx(5.0)
    assert horizon_at(az, el, np.array([315.0]))[0] == pytest.approx(10.0)  # 270 -> 360 (= 0)
    assert horizon_at(az, el, np.array([-45.0]))[0] == pytest.approx(10.0)  # same direction


def test_longest_run() -> None:
    flags = np.array([True, True, False, True, True, True, False])
    assert longest_run_h(flags, True, 0.5) == 1.5
    assert longest_run_h(flags, False, 0.5) == 0.5
    assert longest_run_h(np.array([True, True]), False, 1.0) == 0.0


# --- Metrics on a flat horizon -----------------------------------------------------------------


def test_metrics_on_a_known_sun_series() -> None:
    # Sun elevations hour by hour against a flat 0 degree horizon:
    # visible = F T T F F T  ->  3/6 lit, light runs 2 h and 1 h, dark runs 1 h and 2 h.
    ev = evaluate(FakeEphemeris([-1.0, 1.0, 2.0, -1.0, -2.0, 3.0]))
    m = ev.metrics
    assert ev.sun_visible == [False, True, True, False, False, True]
    assert m.illumination_fraction == pytest.approx(0.5)
    assert m.longest_light_h == 2.0 and m.longest_dark_h == 2.0
    assert m.sun_elevation_max_deg == 3.0
    assert m.sun_elevation_mean_visible_deg == pytest.approx(2.0)  # (1 + 2 + 3) / 3
    assert m.sun_visible_at_start is False
    assert m.next_sunrise_utc == T0 + timedelta(hours=1)  # first sample in the new state
    assert m.next_sunset_utc == T0 + timedelta(hours=3)


def test_run_durations_use_the_window_step() -> None:
    ev = evaluate(FakeEphemeris([1.0, 1.0, 1.0, -1.0], step_min=10), n=4, step_min=10)
    assert ev.metrics.longest_light_h == pytest.approx(0.5)  # 3 samples x 10 min


def test_body_exactly_on_the_horizon_is_hidden() -> None:
    ev = evaluate(FakeEphemeris([0.0, 0.0]), n=2)
    assert ev.sun_visible == [False, False]
    assert ev.metrics.sun_elevation_mean_visible_deg is None
    assert ev.metrics.next_sunrise_utc is None and ev.metrics.next_sunset_utc is None


def test_always_visible_earth_has_no_events() -> None:
    ev = evaluate(FakeEphemeris([5.0] * 4, earth_el=[7.0] * 4), n=4)
    m = ev.metrics
    assert m.earth_visibility_fraction == 1.0 and m.earth_visible_at_start
    assert m.longest_earth_visible_h == 4.0 and m.longest_earth_hidden_h == 0.0
    assert m.next_earthset_utc is None and m.next_earthrise_utc is None


# --- The mask depends on azimuth ---------------------------------------------------------------


def test_same_elevation_is_hidden_behind_a_ridge_and_visible_elsewhere() -> None:
    # A 5 degree ridge between azimuths 80 and 100 (mask at 10 degree steps, flat elsewhere).
    mask_az = [float(a) for a in range(0, 360, 10)]
    mask_el = [5.0 if 80 <= a <= 100 else 0.0 for a in mask_az]
    sun_az = [90.0, 270.0, 85.0, 75.0]  # behind the ridge, open sky, on the ridge, on its flank
    ev = evaluate(FakeEphemeris([3.0] * 4, sun_az=sun_az), FakeTerrain(mask_az, mask_el), n=4)
    # At 75 deg the interpolated mask is 2.5 deg (halfway between 70 -> 0 and 80 -> 5): 3 > 2.5.
    assert ev.sun_visible == [False, True, False, True]


def test_earth_uses_its_own_azimuth() -> None:
    mask_az = [0.0, 90.0, 180.0, 270.0]
    mask_el = [8.0, 0.0, 0.0, 0.0]  # high terrain toward north only
    eph = FakeEphemeris([5.0] * 2, sun_az=[0.0, 0.0], earth_el=[5.0] * 2, earth_az=[180.0, 0.0])
    ev = evaluate(eph, FakeTerrain(mask_az, mask_el), n=2)
    assert ev.sun_visible == [False, False]  # Sun in the north, behind the 8 degree terrain
    assert ev.earth_visible == [True, False]
    assert ev.metrics.next_earthset_utc == T0 + timedelta(hours=1)


# --- EVA-2 and contract ------------------------------------------------------------------------


def test_terrain_statistics_cover_landing_precision_plus_operating_range() -> None:
    terrain = FakeTerrain()
    area = OperationsArea(landing_precision_m=100.0, operating_range_m=2_000.0)
    ev = LunarEvaluator(FakeEphemeris([1.0, 1.0]), terrain).evaluate(SITE, window(2), area, "s1")
    assert terrain.radius_asked == 2_100.0
    assert ev.terrain.radius_m == 2_100.0 and ev.site_id == "s1"


def test_example_payloads_evaluate_to_a_valid_evaluation() -> None:
    series = EphemerisSeries.model_validate_json((EXAMPLES / "ephemeris_series.json").read_text())
    mask = HorizonMask.model_validate_json((EXAMPLES / "horizon_mask.json").read_text())

    class ExampleEphemeris:
        def sun_earth(self, location: GeoPoint, window: TimeWindow) -> EphemerisSeries:
            return series

    terrain = FakeTerrain(mask.azimuth_deg, mask.horizon_elevation_deg)
    step = int((series.times_utc[1] - series.times_utc[0]).total_seconds() // 60)
    win = TimeWindow(start_utc=series.times_utc[0], end_utc=series.times_utc[-1], step_minutes=step)
    ev = build_evaluator(ExampleEphemeris(), terrain).evaluate(
        series.location, win, OperationsArea()
    )
    Evaluation.model_validate(ev.model_dump())
    assert len(ev.sun_visible) == len(series.times_utc)
