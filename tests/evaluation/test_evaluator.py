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
from lunarnav.evaluation.visibility import horizon_at, longest_run

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
    assert longest_run(flags, True, 0.5) == (1.5, False)  # the 3-sample run is inside
    assert longest_run(flags, False, 0.5) == (0.5, True)  # one of the 1-sample runs ends the window
    assert longest_run(np.array([True, True]), False, 1.0) == (0.0, False)


def test_truncation_follows_the_longest_runs_only() -> None:
    edge_short = np.array([True, False, True, True, False])  # edge run shorter than inner run
    assert longest_run(edge_short, True, 1.0) == (2.0, False)
    tie = np.array([True, True, False, True, True, False])  # one of the tied runs is at the edge
    assert longest_run(tie, True, 1.0) == (2.0, True)


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


# --- Decision D29 fields ------------------------------------------------------------------------


def test_horizon_per_sample_is_the_threshold_used() -> None:
    mask_az = [0.0, 90.0, 180.0, 270.0]
    mask_el = [0.0, 10.0, 0.0, 20.0]
    eph = FakeEphemeris(
        [4.0, 12.0], sun_az=[45.0, 315.0], earth_el=[1.0, 1.0], earth_az=[90.0, 0.0]
    )
    ev = evaluate(eph, FakeTerrain(mask_az, mask_el), n=2)
    assert ev.sun_horizon_elevation_deg == pytest.approx([5.0, 10.0])  # 45 -> 5, 315 -> 10
    assert ev.sun_visible == [False, True]
    assert ev.earth_horizon_elevation_deg == pytest.approx([10.0, 0.0])
    assert ev.earth_visible == [False, True]


def test_joint_fraction_earth_mean_and_truncation() -> None:
    # Sun visible  T T T F F T ; Earth visible T T F F T T  (flat horizon)
    sun = [5.0, 6.0, 7.0, -1.0, -2.0, 4.0]
    earth = [3.0, 1.0, -1.0, -2.0, 2.0, 4.0]
    m = evaluate(FakeEphemeris(sun, earth_el=earth)).metrics
    assert m.sun_and_earth_visible_fraction == pytest.approx(3 / 6)
    assert m.earth_elevation_mean_visible_deg == pytest.approx((3 + 1 + 2 + 4) / 4)
    assert (m.longest_light_h, m.longest_light_truncated) == (3.0, True)
    assert (m.longest_dark_h, m.longest_dark_truncated) == (2.0, False)
    assert (m.longest_earth_visible_h, m.longest_earth_visible_truncated) == (2.0, True)
    assert (m.longest_earth_hidden_h, m.longest_earth_hidden_truncated) == (2.0, False)


def test_metrics_agree_with_the_reference_definitions_on_random_series() -> None:
    # Gian's reference implementation pins the spec section 3 definitions (decision D29).
    reference = pytest.importorskip("lunarnav.api.placeholder_metrics")
    from lunarnav.evaluation.evaluator import compute_metrics

    rng = np.random.default_rng(42)
    for _ in range(200):
        n = int(rng.integers(1, 40))
        sun_el = rng.uniform(-5.0, 5.0, n)
        earth_el = rng.uniform(-5.0, 5.0, n)
        sun_vis, earth_vis = sun_el > 0.0, earth_el > 0.0
        times = [T0 + timedelta(hours=i) for i in range(n)]
        ours = compute_metrics(times, sun_el, sun_vis, earth_el, earth_vis, window(max(n, 2)))
        ref = reference.compute_metrics(
            times, sun_el.tolist(), sun_vis.tolist(), earth_el.tolist(), earth_vis.tolist(), 1.0
        )
        for name, value in ref.model_dump().items():
            mine = getattr(ours, name)
            if isinstance(value, float) and not isinstance(value, bool):
                assert mine == pytest.approx(value), (name, n)
            else:
                assert mine == value, (name, n)
