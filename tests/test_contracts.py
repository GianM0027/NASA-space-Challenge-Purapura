# ABOUTME: Tests of the shared contracts: examples validate, validators reject bad data
# ABOUTME: Owner: Gian; this is also the repo smoke test every PR must keep green

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from lunarnav.contracts import (
    AiAnswer,
    EphemerisSeries,
    Evaluation,
    GeoPoint,
    HorizonMask,
    MissionRequirements,
    Origin,
    RobustnessReport,
    Site,
    SiteRanking,
    TerrainStats,
    TimeWindow,
)

EXAMPLES = Path(__file__).resolve().parents[1] / "data" / "examples"

SINGLE_MODEL_EXAMPLES = {
    "ephemeris_series.json": EphemerisSeries,
    "horizon_mask.json": HorizonMask,
    "terrain_stats.json": TerrainStats,
    "evaluation.json": Evaluation,
    "mission_requirements.json": MissionRequirements,
    "site_ranking.json": SiteRanking,
    "ai_answer.json": AiAnswer,
    "robustness_report.json": RobustnessReport,
}


@pytest.mark.parametrize(("filename", "model"), SINGLE_MODEL_EXAMPLES.items())
def test_example_payload_matches_contract(filename: str, model: type) -> None:
    model.model_validate_json((EXAMPLES / filename).read_text(encoding="utf-8"))


def test_example_sites_match_contract() -> None:
    sites = TypeAdapter(list[Site]).validate_json(
        (EXAMPLES / "sites.json").read_text(encoding="utf-8")
    )
    assert len(sites) >= 2


def test_time_window_rejects_end_before_start() -> None:
    start = datetime(2027, 1, 1, tzinfo=UTC)
    with pytest.raises(ValidationError):
        TimeWindow(start_utc=start, end_utc=start)


def test_time_window_rejects_naive_datetimes() -> None:
    with pytest.raises(ValidationError):
        TimeWindow(start_utc=datetime(2027, 1, 1), end_utc=datetime(2027, 1, 2))


def test_longitude_must_be_east_positive_in_minus180_180() -> None:
    with pytest.raises(ValidationError):
        GeoPoint(lat_deg=0.0, lon_deg=180.0)


def test_misaligned_series_are_rejected() -> None:
    with pytest.raises(ValidationError):
        HorizonMask(
            location=GeoPoint(lat_deg=0.0, lon_deg=0.0),
            azimuth_deg=[0.0, 90.0],
            horizon_elevation_deg=[0.0],
            dem_source="test",
            dem_resolution_m=100.0,
            max_distance_m=1000.0,
        )


def test_catalog_site_needs_a_source_but_user_site_does_not() -> None:
    point = GeoPoint(lat_deg=0.0, lon_deg=0.0)
    with pytest.raises(ValidationError):
        Site(id="no-source", name="X", location=point, origin=Origin.APOLLO, status="landed")
    Site(id="mine", name="Mine", location=point, origin=Origin.USER, status="custom")


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        GeoPoint.model_validate({"lat_deg": 0.0, "lon_deg": 0.0, "altitude": 3.0})
