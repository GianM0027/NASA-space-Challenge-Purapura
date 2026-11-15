# ABOUTME: Known-answer tests of the deterministic ranking (spec AI-2): ROC weights, margins, order
# ABOUTME: Owner: Gian. Fixed metrics in, expected order and scores out; fake catalog and evaluator

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from lunarnav.ai.archetypes import Archetype
from lunarnav.ai.ranking import (
    CRITERIA_BY_FIELD,
    CatalogRanker,
    SiteResult,
    criterion_weights,
    margin_and_shortfall,
    roc_weights,
    score_sites,
)
from lunarnav.contracts import (
    Evaluation,
    GeoPoint,
    MissionRequirements,
    OperationsArea,
    Origin,
    Site,
    TimeWindow,
    VisibilityMetrics,
)

EXAMPLES = Path(__file__).resolve().parents[2] / "data" / "examples"
START = datetime(2026, 11, 14, tzinfo=UTC)
WINDOW = TimeWindow(start_utc=START, end_utc=START + timedelta(hours=100), step_minutes=60)


def _metrics(**update: object) -> VisibilityMetrics:
    base = Evaluation.model_validate_json((EXAMPLES / "evaluation.json").read_text()).metrics
    return base.model_copy(update=update)


def test_roc_weights_three_items_match_barron_barrett() -> None:
    weights = roc_weights([["a"], ["b"], ["c"]])
    assert weights == pytest.approx({"a": 11 / 18, "b": 5 / 18, "c": 2 / 18})


def test_roc_weights_tied_items_share_the_mean_of_their_positions() -> None:
    weights = roc_weights([["a"], ["b", "c"]])
    assert weights["a"] == pytest.approx(11 / 18)
    assert weights["b"] == weights["c"] == pytest.approx((5 / 18 + 2 / 18) / 2)
    assert sum(weights.values()) == pytest.approx(1.0)


def test_criterion_weights_ignore_unset_priority_and_append_the_rest() -> None:
    weights = criterion_weights(
        ["max_slope_deg", "min_illumination_fraction", "min_earth_visibility_fraction"],
        priority=[["min_continuous_light_h"], ["min_earth_visibility_fraction"]],
    )
    assert weights["min_earth_visibility_fraction"] == pytest.approx(11 / 18)
    assert weights["max_slope_deg"] == weights["min_illumination_fraction"]
    assert sum(weights.values()) == pytest.approx(1.0)


def test_criterion_weights_without_priority_are_equal() -> None:
    assert criterion_weights(["a", "b"]) == pytest.approx({"a": 0.5, "b": 0.5})


def test_margin_min_uses_the_headroom_to_the_top_of_the_range() -> None:
    criterion = CRITERIA_BY_FIELD["min_illumination_fraction"]
    assert margin_and_shortfall(criterion, 0.75, 0.5, 100.0) == pytest.approx((True, 0.5, 0.0))
    assert margin_and_shortfall(criterion, 0.25, 0.5, 100.0) == pytest.approx((False, 0.0, 0.5))


def test_margin_max_slope_and_threshold_at_the_edge() -> None:
    slope = CRITERIA_BY_FIELD["max_slope_deg"]
    assert margin_and_shortfall(slope, 2.0, 10.0, 100.0) == pytest.approx((True, 0.8, 0.0))
    light = CRITERIA_BY_FIELD["min_continuous_light_h"]
    assert margin_and_shortfall(light, 100.0, 100.0, 100.0) == pytest.approx((True, 1.0, 0.0))
    assert margin_and_shortfall(light, None, 50.0, 100.0) == (False, 0.0, 1.0)


def test_score_sites_orders_passing_then_closest_failing() -> None:
    requirements = MissionRequirements(
        window=WINDOW, min_illumination_fraction=0.5, max_slope_deg=10.0
    )
    weights = {"min_illumination_fraction": 0.5, "max_slope_deg": 0.5}
    results = [
        SiteResult("fails-both", _metrics(illumination_fraction=0.1), 30.0),
        SiteResult("good", _metrics(illumination_fraction=0.75), 2.0),
        SiteResult("fails-slope", _metrics(illumination_fraction=0.9), 12.0),
        SiteResult("better", _metrics(illumination_fraction=1.0), 2.0),
    ]
    scores = score_sites(requirements, results, weights)
    assert [s.site_id for s in scores] == ["better", "good", "fails-slope", "fails-both"]
    assert [s.rank for s in scores] == [1, 2, 3, 4]
    assert scores[0].score == pytest.approx(0.5 * 1.0 + 0.5 * 0.8)
    assert scores[1].score == pytest.approx(0.5 * 0.5 + 0.5 * 0.8)
    assert scores[2].score == 0.0
    assert scores[2].constraints_met == {"min_illumination_fraction": True, "max_slope_deg": False}
    assert scores[2].criterion_values == {"min_illumination_fraction": 0.9, "max_slope_deg": 12.0}


def test_score_sites_needs_a_criterion() -> None:
    with pytest.raises(ValueError, match="at least one"):
        score_sites(MissionRequirements(window=WINDOW), [], {})


class _Catalog:
    def __init__(self, sites: list[Site]) -> None:
        self.sites = sites

    def list_sites(self) -> list[Site]:
        return self.sites


class _Evaluator:
    """Returns the example evaluation with per-site illumination; raises for 'broken'."""

    def __init__(self, light: dict[str, float]) -> None:
        self.light = light
        self.areas: list[OperationsArea] = []

    def evaluate(
        self, location: GeoPoint, window: TimeWindow, area: OperationsArea, site_id: str | None
    ) -> Evaluation:
        if site_id == "broken":
            raise RuntimeError("DEM missing")
        self.areas.append(area)
        base = Evaluation.model_validate_json((EXAMPLES / "evaluation.json").read_text())
        metrics = base.metrics.model_copy(update={"illumination_fraction": self.light[site_id]})
        return base.model_copy(update={"metrics": metrics})


def _site(site_id: str, lat: float, origin: Origin = Origin.ARTEMIS) -> Site:
    return Site(
        id=site_id,
        name=site_id,
        location=GeoPoint(lat_deg=lat, lon_deg=0.0),
        origin=origin,
        status="candidate",
        sources=["test"],
    )


def test_catalog_ranker_filters_scope_and_reports_unavailable_sites() -> None:
    catalog = _Catalog(
        [_site("north", 10.0), _site("pole", -89.0), _site("broken", -88.0), _site("rim", -87.0)]
    )
    evaluator = _Evaluator({"pole": 0.9, "rim": 0.6, "north": 1.0})
    area = OperationsArea(landing_precision_m=100.0)
    requirements = MissionRequirements(
        window=WINDOW, area=area, min_illumination_fraction=0.5, latitude_max_deg=-80.0
    )
    ranking = CatalogRanker(catalog, evaluator, {}).rank(requirements)
    assert [s.site_id for s in ranking.results] == ["pole", "rim"]
    assert set(ranking.unavailable) == {"broken"}
    assert ranking.weights == {"min_illumination_fraction": 1.0}
    assert evaluator.areas == [area, area]


def test_catalog_ranker_takes_weights_from_the_archetype_priority() -> None:
    archetype = Archetype(
        id="crew",
        name="Crew",
        summary="",
        mission_duration_h=None,
        requirements=MissionRequirements(),
        priority=(("max_slope_deg",), ("min_illumination_fraction",)),
        sources={},
        notes=(),
    )
    ranker = CatalogRanker(_Catalog([]), _Evaluator({}), {"crew": archetype})
    weights = ranker.weights(
        MissionRequirements(min_illumination_fraction=0.5, max_slope_deg=10.0, archetype_id="crew")
    )
    assert weights == pytest.approx({"max_slope_deg": 0.75, "min_illumination_fraction": 0.25})
