# ABOUTME: Known-answer tests for the mission analyzer (MA-1, MA-2, MA-3) with a fake Evaluator
# ABOUTME: Owner: Michael (D37); the fake encodes shift and position in the metrics it returns

import math
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from lunarnav.contracts import Evaluation, GeoPoint, MissionAnalyzer, OperationsArea, TimeWindow
from lunarnav.mission_analysis import (
    DEFAULT_SHIFTS_DAYS,
    RobustnessAnalyzer,
    build_mission_analyzer,
)
from lunarnav.mission_analysis.analyzer import destination, sample_points, shift_window

EXAMPLE = Evaluation.model_validate_json(
    (Path(__file__).parents[2] / "data/examples/evaluation.json").read_text(encoding="utf-8")
)
T0 = datetime(2026, 12, 1, tzinfo=UTC)
WINDOW = TimeWindow(start_utc=T0, end_utc=T0 + timedelta(days=14), step_minutes=60)
SITE = GeoPoint(lat_deg=-85.0, lon_deg=30.0)
METERS_PER_DEG = 1_737_400.0 * math.pi / 180  # arc length of 1 deg on the reference sphere


class FakeEvaluator:
    """Illumination = 0.50 + 0.01 * shift_days - 0.1 * km from SITE; slope = 2 deg per km."""

    def __init__(self) -> None:
        self.calls: list[tuple[GeoPoint, TimeWindow, OperationsArea]] = []

    def evaluate(self, location, window, area, site_id=None) -> Evaluation:
        self.calls.append((location, window, area))
        shift = (window.start_utc - T0).total_seconds() / 86400
        km = _distance_m(SITE, location) / 1000
        metrics = EXAMPLE.metrics.model_copy(
            update={
                "illumination_fraction": round(0.50 + 0.01 * shift - 0.1 * km, 6),
                "longest_dark_h": 10.0 + shift,
            }
        )
        terrain = EXAMPLE.terrain.model_copy(update={"landing_slope_max_deg": 2.0 * km})
        return EXAMPLE.model_copy(update={"metrics": metrics, "terrain": terrain})


def _distance_m(a: GeoPoint, b: GeoPoint) -> float:
    la, lb = math.radians(a.lat_deg), math.radians(b.lat_deg)
    dlon = math.radians(b.lon_deg - a.lon_deg)
    c = math.sin(la) * math.sin(lb) + math.cos(la) * math.cos(lb) * math.cos(dlon)
    return 1_737_400.0 * math.acos(max(-1.0, min(1.0, c)))


def _analyze(area: OperationsArea, shifts: list[float]):
    fake = FakeEvaluator()
    report = RobustnessAnalyzer(fake).analyze(SITE, WINDOW, area, shifts, site_id="test-site")
    return report, fake


# --- geometry ---------------------------------------------------------------------------------


def test_destination_one_degree_north_and_east_at_equator() -> None:
    north = destination(GeoPoint(lat_deg=0.0, lon_deg=0.0), METERS_PER_DEG, 0.0)
    assert north.lat_deg == pytest.approx(1.0, abs=1e-9)
    assert north.lon_deg == pytest.approx(0.0, abs=1e-9)
    east = destination(GeoPoint(lat_deg=0.0, lon_deg=179.5), METERS_PER_DEG, 90.0)
    assert east.lon_deg == pytest.approx(-179.5, abs=1e-9)  # wraps across 180


def test_destination_keeps_distance_near_the_pole() -> None:
    pole_site = GeoPoint(lat_deg=-89.9, lon_deg=0.0)
    for az in (0, 90, 180, 270):
        point = destination(pole_site, 5000.0, az)
        assert _distance_m(pole_site, point) == pytest.approx(5000.0, rel=1e-6)


def test_sample_points_rings_and_count() -> None:
    points = sample_points(SITE, 2000.0, rings=2, points_per_ring=4)
    assert [r for r, _ in points] == [1000.0] * 4 + [2000.0] * 4
    for r, p in points:
        assert _distance_m(SITE, p) == pytest.approx(r, rel=1e-6)
    assert sample_points(SITE, 0.0, 2, 4) == []


def test_shift_window_keeps_length_and_step() -> None:
    w = shift_window(WINDOW, 3)
    assert w.start_utc == T0 + timedelta(days=3)
    assert w.end_utc - w.start_utc == WINDOW.end_utc - WINDOW.start_utc
    assert w.step_minutes == WINDOW.step_minutes


# --- MA-1, MA-2 -------------------------------------------------------------------------------


def test_date_shifts_evaluate_the_shifted_windows() -> None:
    report, _ = _analyze(OperationsArea(), [1, 7])
    assert [s.shift_days for s in report.date_shifts] == [1, 7]
    assert report.date_shifts[0].metrics.illumination_fraction == pytest.approx(0.51)
    assert report.date_shifts[1].metrics.illumination_fraction == pytest.approx(0.57)
    assert report.nominal.illumination_fraction == pytest.approx(0.50)
    assert report.site_id == "test-site"


def test_empty_shift_list_uses_the_spec_defaults() -> None:
    report, _ = _analyze(OperationsArea(), [])
    assert [s.shift_days for s in report.date_shifts] == list(DEFAULT_SHIFTS_DAYS) == [1, 3, 7, 14]


def test_dispersion_samples_the_operations_disk() -> None:
    area = OperationsArea(landing_precision_m=100, operating_range_m=1900)
    report, fake = _analyze(area, [1])
    assert len(report.dispersion) == 8  # 2 rings x 4 points, center excluded
    assert {s.offset_m for s in report.dispersion} == {1000.0, 2000.0}
    edge = [s for s in report.dispersion if s.offset_m == 2000.0]
    assert all(s.metrics.illumination_fraction == pytest.approx(0.30) for s in edge)
    assert all(s.slope_max_deg == pytest.approx(4.0) for s in edge)
    # samples are evaluated as landing points: operating range dropped, rest of the area kept
    sample_areas = [a for _, _, a in fake.calls[2:]]
    assert all(a.operating_range_m == 0 and a.landing_precision_m == 100 for a in sample_areas)


def test_no_dispersion_without_an_area() -> None:
    report, fake = _analyze(OperationsArea(), [1])
    assert report.dispersion == []
    assert len(fake.calls) == 2  # nominal + one shift


# --- MA-3 -------------------------------------------------------------------------------------


def test_summary_quotes_only_report_numbers() -> None:
    area = OperationsArea(landing_precision_m=0, operating_range_m=2000)
    report, _ = _analyze(area, [1, 14])
    s = report.summary
    assert s is not None
    assert "50%" in s  # nominal sunlight
    assert "51%" in s and "64%" in s  # shifts +1 d and +14 d
    assert "24 h" in s  # longest darkness at +14 d = 10 + 14
    assert "30%" in s and "40%" in s  # dispersion worst (2 km) and best (1 km)
    assert "4.0 deg" in s
    # Every number in the text must come from the report: metric values, shifts, offsets, counts.
    n = report.nominal
    allowed = {"50", "51", "64", "24", "30", "40", "4.0", "8", "2000", "1000", "+1", "+14"}
    allowed |= {f"{100 * n.earth_visibility_fraction:.0f}", f"{n.longest_dark_h:.0f}"}
    numbers = set(re.findall(r"[+-]?\d+(?:\.\d+)?", s))
    assert numbers <= allowed, numbers - allowed


def test_factory_returns_the_port() -> None:
    analyzer: MissionAnalyzer = build_mission_analyzer(FakeEvaluator())
    assert isinstance(analyzer, RobustnessAnalyzer)
