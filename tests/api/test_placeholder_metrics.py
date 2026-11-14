# ABOUTME: Known-answer tests of the placeholder metrics and horizon interpolation used by the API
# ABOUTME: Owner: Gian; the same definitions (spec section 3) bind Federico's real evaluator

from datetime import UTC, datetime, timedelta

import pytest

from lunarnav.api.placeholder_metrics import compute_metrics, horizon_at, longest_run

T0 = datetime(2027, 1, 1, tzinfo=UTC)
STEP_H = 1.0


def _times(n: int) -> list[datetime]:
    return [T0 + timedelta(hours=i) for i in range(n)]


# --- longest_run: duration and truncation -----------------------------------------------------


def test_run_in_the_middle_is_not_truncated() -> None:
    assert longest_run([False, True, True, False], True, STEP_H) == (2.0, False)


def test_run_touching_the_start_is_truncated() -> None:
    assert longest_run([True, True, False, True], True, STEP_H) == (2.0, True)


def test_run_touching_the_end_is_truncated() -> None:
    assert longest_run([False, True, False, True, True], True, STEP_H) == (2.0, True)


def test_any_longest_run_touching_an_edge_truncates() -> None:
    # Two runs of the maximal length: the inner one is complete, the edge one is not.
    assert longest_run([True, True, False, True, True, False], True, STEP_H) == (2.0, True)


def test_shorter_edge_run_does_not_truncate_a_longer_inner_one() -> None:
    assert longest_run([True, False, True, True, False], True, STEP_H) == (2.0, False)


def test_absent_state_has_zero_length_and_is_not_truncated() -> None:
    assert longest_run([False, False], True, STEP_H) == (0.0, False)


def test_run_scales_with_the_step() -> None:
    assert longest_run([False, True, True, True, False], True, 0.5) == (1.5, False)


# --- horizon_at: interpolation with wrap-around -----------------------------------------------


AZ = [0.0, 90.0, 180.0, 270.0]
EL = [0.0, 10.0, 20.0, 30.0]


def test_horizon_on_a_grid_azimuth() -> None:
    assert horizon_at(AZ, EL, 90.0) == pytest.approx(10.0)


def test_horizon_between_grid_azimuths() -> None:
    assert horizon_at(AZ, EL, 135.0) == pytest.approx(15.0)


def test_horizon_wraps_from_last_azimuth_to_the_first() -> None:
    # Halfway from 270 deg (30) to 360 deg = 0 deg (0).
    assert horizon_at(AZ, EL, 315.0) == pytest.approx(15.0)


def test_horizon_accepts_azimuth_outside_0_360() -> None:
    assert horizon_at(AZ, EL, -45.0) == pytest.approx(15.0)
    assert horizon_at(AZ, EL, 450.0) == pytest.approx(10.0)


# --- compute_metrics: joint visibility, Earth mean, truncation --------------------------------


def test_metrics_known_answer() -> None:
    times = _times(6)
    sun_el = [5.0, 6.0, 7.0, -1.0, -2.0, 4.0]
    sun_vis = [True, True, True, False, False, True]
    earth_el = [3.0, 1.0, -1.0, -2.0, 2.0, 4.0]
    earth_vis = [True, True, False, False, True, True]
    m = compute_metrics(times, sun_el, sun_vis, earth_el, earth_vis, STEP_H)

    assert m.illumination_fraction == pytest.approx(4 / 6)
    assert m.earth_visibility_fraction == pytest.approx(4 / 6)
    # Both visible at samples 0, 1 and 5.
    assert m.sun_and_earth_visible_fraction == pytest.approx(3 / 6)
    assert m.sun_elevation_mean_visible_deg == pytest.approx((5 + 6 + 7 + 4) / 4)
    assert m.earth_elevation_mean_visible_deg == pytest.approx((3 + 1 + 2 + 4) / 4)
    assert (m.longest_light_h, m.longest_light_truncated) == (3.0, True)
    assert (m.longest_dark_h, m.longest_dark_truncated) == (2.0, False)
    assert (m.longest_earth_visible_h, m.longest_earth_visible_truncated) == (2.0, True)
    assert (m.longest_earth_hidden_h, m.longest_earth_hidden_truncated) == (2.0, False)
    assert m.next_sunset_utc == times[3]
    assert m.next_sunrise_utc == times[5]
    assert m.next_earthset_utc == times[2]
    assert m.next_earthrise_utc == times[4]


def test_earth_never_visible_has_no_mean_elevation() -> None:
    times = _times(2)
    m = compute_metrics(times, [1.0, 1.0], [True, True], [-5.0, -5.0], [False, False], STEP_H)
    assert m.earth_elevation_mean_visible_deg is None
    assert m.sun_and_earth_visible_fraction == 0.0
