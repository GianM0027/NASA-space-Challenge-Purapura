# ABOUTME: Writes data/examples/*.json: synthetic contract-valid payloads for parallel work
# ABOUTME: Owner: Gian. Illustrative numbers, never real lunar data; rerun after contract changes

"""Write synthetic example payloads for every contract model into ``data/examples/``.

Run with ``uv run python scripts/contracts_make_examples.py``. Every payload is labelled
"SYNTHETIC EXAMPLE" in its source fields: these values exist to exercise code paths and
UI layouts, not to describe the Moon.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, TypeAdapter

from lunarnav.api.placeholder_metrics import compute_metrics
from lunarnav.contracts import (
    AiAnswer,
    DateShiftResult,
    DispersionSample,
    EphemerisSeries,
    Evaluation,
    GeoPoint,
    HorizonMask,
    MissionRequirements,
    OperationsArea,
    Origin,
    RobustnessReport,
    Site,
    SiteRanking,
    SiteScore,
    TerrainStats,
    TimeWindow,
)

OUT = Path(__file__).resolve().parents[1] / "data" / "examples"
LABEL = "SYNTHETIC EXAMPLE, not real data"
STEP_MIN = 240


def _dump(name: str, payload: BaseModel | list[Site]) -> None:
    """Write one payload as indented JSON."""
    if isinstance(payload, list):
        text = TypeAdapter(list[Site]).dump_json(payload, indent=2).decode()
    else:
        text = payload.model_dump_json(indent=2)
    (OUT / name).write_text(text + "\n", encoding="utf-8")


def main() -> None:
    """Build every example payload and write it to ``data/examples/``."""
    OUT.mkdir(parents=True, exist_ok=True)
    point = GeoPoint(lat_deg=-89.5, lon_deg=0.0, height_m=1500.0)
    start = datetime(2027, 1, 1, tzinfo=UTC)
    window = TimeWindow(start_utc=start, end_utc=start + timedelta(days=2), step_minutes=STEP_MIN)
    area = OperationsArea(landing_precision_m=100.0, operating_range_m=500.0)
    times = [start + timedelta(minutes=STEP_MIN * i) for i in range(13)]
    sun_az = [(30.0 * i) % 360.0 for i in range(13)]
    sun_el = [-2.0, -1.0, 0.5, 1.5, 2.5, 3.0, 3.2, 3.0, 2.5, 1.5, 0.5, -1.0, -2.0]
    earth_az = [2.0] * 13
    earth_el = [1.5] * 13
    azimuths = [10.0 * i for i in range(36)]
    horizon = HorizonMask(
        location=point,
        azimuth_deg=azimuths,
        horizon_elevation_deg=[0.0] * 36,
        dem_source=LABEL,
        dem_resolution_m=60.0,
        max_distance_m=50_000.0,
    )
    sun_vis = [e > 0.0 for e in sun_el]
    earth_vis = [e > 0.0 for e in earth_el]
    metrics = compute_metrics(times, sun_el, sun_vis, earth_el, earth_vis, STEP_MIN / 60.0)
    terrain = TerrainStats(
        location=point,
        radius_m=600.0,
        elevation_m=1500.0,
        slope_mean_deg=4.0,
        slope_max_deg=11.0,
        landing_radius_m=area.landing_precision_m,
        landing_slope_mean_deg=2.0,
        landing_slope_max_deg=5.0,
        traverse_slope_limit_deg=area.traverse_slope_limit_deg,
        reachable_fraction=0.9,
        dem_source=LABEL,
        dem_resolution_m=60.0,
    )
    sites = [
        Site(
            id="example-polar",
            name="Synthetic polar site",
            location=point,
            origin=Origin.OTHER,
            status="candidate",
            description="Synthetic example of a high-latitude candidate site.",
            sources=[LABEL],
        ),
        Site(
            id="example-user",
            name="Synthetic user site",
            location=GeoPoint(lat_deg=10.0, lon_deg=-20.0),
            origin=Origin.USER,
            status="custom",
            description="Synthetic example of a user-added site.",
        ),
    ]
    requirements = MissionRequirements(
        window=window,
        area=area,
        min_illumination_fraction=0.6,
        min_earth_visibility_fraction=0.9,
        max_slope_deg=15.0,
        latitude_max_deg=-80.0,
        rationale={
            "min_illumination_fraction": "Synthetic example rationale.",
            "max_slope_deg": "Synthetic example rationale.",
        },
        source_request="Synthetic example: a polar rover that recharges most of the time.",
    )
    ranking = SiteRanking(
        requirements=requirements,
        results=[
            SiteScore(
                site_id="example-polar",
                rank=1,
                score=0.8,
                constraints_met={
                    "min_illumination_fraction": True,
                    "min_earth_visibility_fraction": True,
                    "max_slope_deg": True,
                    "latitude_max_deg": True,
                },
                all_constraints_met=True,
                metrics=metrics,
                landing_slope_max_deg=terrain.landing_slope_max_deg,
                rationale="Synthetic example rationale.",
            )
        ],
    )
    _dump("sites.json", sites)
    _dump(
        "ephemeris_series.json",
        EphemerisSeries(
            location=point,
            times_utc=times,
            sun_azimuth_deg=sun_az,
            sun_elevation_deg=sun_el,
            earth_azimuth_deg=earth_az,
            earth_elevation_deg=earth_el,
            source=LABEL,
        ),
    )
    _dump("horizon_mask.json", horizon)
    _dump("terrain_stats.json", terrain)
    _dump(
        "evaluation.json",
        Evaluation(
            site_id="example-polar",
            location=point,
            window=window,
            area=area,
            times_utc=times,
            sun_azimuth_deg=sun_az,
            sun_elevation_deg=sun_el,
            sun_horizon_elevation_deg=[0.0] * 13,
            sun_visible=sun_vis,
            earth_azimuth_deg=earth_az,
            earth_elevation_deg=earth_el,
            earth_horizon_elevation_deg=[0.0] * 13,
            earth_visible=earth_vis,
            horizon=horizon,
            terrain=terrain,
            metrics=metrics,
        ),
    )
    _dump("mission_requirements.json", requirements)
    _dump("site_ranking.json", ranking)
    _dump(
        "ai_answer.json",
        AiAnswer(requirements=requirements, ranking=ranking, message=LABEL),
    )
    _dump(
        "robustness_report.json",
        RobustnessReport(
            site_id="example-polar",
            nominal=metrics,
            date_shifts=[
                DateShiftResult(shift_days=1.0, metrics=metrics),
                DateShiftResult(shift_days=7.0, metrics=metrics),
            ],
            dispersion=[
                DispersionSample(location=point, offset_m=0.0, metrics=metrics, slope_max_deg=11.0),
            ],
            summary=LABEL,
        ),
    )


if __name__ == "__main__":
    main()
