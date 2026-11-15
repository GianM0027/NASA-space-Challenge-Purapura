# ABOUTME: Deterministic ranking of catalog sites against mission requirements (spec AI-2)
# ABOUTME: Owner: Gian. Hard filters, weighted margin score, ROC weights from archetype priority

"""Deterministic site ranking.

Method:

* Every set criterion (a ``MissionRequirements`` constraint) is a hard filter. A site that meets
  all of them gets ``score = sum(w_c * margin_c)``, where the margin is the share of the
  remaining headroom the site uses up: for a minimum ``(value - threshold) / (upper - threshold)``,
  for a maximum ``(threshold - value) / (threshold - lower)``, with ``[lower, upper]`` the range
  the metric can take (fractions [0, 1], durations [0, window length], angles [-90, 90] or
  [0, 90]). A threshold at the edge of the range leaves no headroom: the margin is then 1.
* A site that violates a criterion scores 0 and is ranked after every passing site, by number of
  violated criteria and then by weighted shortfall (the violation as a share of the distance from
  the threshold to the far end of the range).
* Weights are rank order centroid (ROC) weights over the archetype's priority groups (Barron and
  Barrett 1996, "Decision quality using ranked attribute weights", Management Science 42(11),
  1515-1523, Eq. for w_k); criteria in one group share the mean weight of their positions.
  Criteria the priority does not mention form a last group; without an archetype all set
  criteria weigh the same.
* Latitude bounds and origins are search scope: sites outside them are not ranked at all.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from lunarnav.ai.archetypes import Archetype
from lunarnav.contracts import (
    Evaluator,
    MissionRequirements,
    OperationsArea,
    SiteCatalog,
    SiteRanking,
    SiteScore,
    TimeWindow,
    VisibilityMetrics,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Criterion:
    """One scored constraint of ``MissionRequirements``.

    Attributes:
        field: Requirement field name (the threshold).
        kind: "min" when the site value must reach the threshold, "max" when it must not exceed it.
        label: Short English name of the compared quantity, for explanations.
        unit: "fraction", "h" or "deg"; decides the range and the formatting.
        value: Site value compared with the threshold, from the metrics and the landing-disk
            maximum slope (degrees); None when the metric is undefined (e.g. Sun never visible).
    """

    field: str
    kind: Literal["min", "max"]
    label: str
    unit: Literal["fraction", "h", "deg"]
    value: Callable[[VisibilityMetrics, float], float | None]

    def bounds(self, window_h: float) -> tuple[float, float]:
        """Return the range ``[lower, upper]`` the compared value can take.

        Args:
            window_h: Length of the evaluated window, hours (the longest possible run).
        """
        if self.unit == "fraction":
            return 0.0, 1.0
        if self.unit == "h":
            return 0.0, window_h
        if self.field == "max_slope_deg":
            return 0.0, 90.0
        return -90.0, 90.0


CRITERIA: tuple[Criterion, ...] = (
    Criterion(
        "min_illumination_fraction",
        "min",
        "time in sunlight",
        "fraction",
        lambda m, _: m.illumination_fraction,
    ),
    Criterion(
        "min_continuous_light_h", "min", "longest light", "h", lambda m, _: m.longest_light_h
    ),
    Criterion("max_continuous_dark_h", "max", "longest dark", "h", lambda m, _: m.longest_dark_h),
    Criterion(
        "min_sun_elevation_deg",
        "min",
        "mean Sun elevation when visible",
        "deg",
        lambda m, _: m.sun_elevation_mean_visible_deg,
    ),
    Criterion(
        "min_earth_visibility_fraction",
        "min",
        "time with Earth visible",
        "fraction",
        lambda m, _: m.earth_visibility_fraction,
    ),
    Criterion(
        "min_continuous_earth_visibility_h",
        "min",
        "longest Earth contact",
        "h",
        lambda m, _: m.longest_earth_visible_h,
    ),
    Criterion(
        "max_earth_outage_h",
        "max",
        "longest Earth outage",
        "h",
        lambda m, _: m.longest_earth_hidden_h,
    ),
    Criterion(
        "min_sun_and_earth_visible_fraction",
        "min",
        "time with Sun and Earth both visible",
        "fraction",
        lambda m, _: m.sun_and_earth_visible_fraction,
    ),
    Criterion("max_slope_deg", "max", "landing slope", "deg", lambda _, slope: slope),
)
CRITERIA_BY_FIELD: dict[str, Criterion] = {c.field: c for c in CRITERIA}


def set_criteria(requirements: MissionRequirements) -> list[Criterion]:
    """Return the criteria that have a threshold in ``requirements``, in ``CRITERIA`` order."""
    return [c for c in CRITERIA if getattr(requirements, c.field) is not None]


def roc_weights(groups: Sequence[Sequence[str]]) -> dict[str, float]:
    """Rank order centroid weights for ordered groups of tied items.

    With n items in total, position k (1-based) has weight ``(1/n) * sum_{i=k..n} 1/i``
    (Barron and Barrett 1996); each item gets the mean weight of the positions its group covers.

    Args:
        groups: Item names, most important group first; every name appears once.

    Returns:
        Name -> weight; the weights sum to 1. Empty for no items.
    """
    n = sum(len(group) for group in groups)
    position = [sum(1.0 / i for i in range(k, n + 1)) / n for k in range(1, n + 1)]
    weights: dict[str, float] = {}
    start = 0
    for group in groups:
        share = sum(position[start : start + len(group)]) / len(group) if group else 0.0
        for name in group:
            weights[name] = share
        start += len(group)
    return weights


def criterion_weights(
    fields: Sequence[str], priority: Sequence[Sequence[str]] = ()
) -> dict[str, float]:
    """Weights of the set criteria from an archetype's priority order.

    Args:
        fields: Criterion field names that have a threshold.
        priority: Priority groups of the archetype, most important first (may be empty).

    Returns:
        Field -> weight over ``fields`` only, summing to 1.
    """
    remaining = list(fields)
    groups: list[list[str]] = []
    for group in priority:
        kept = [name for name in group if name in remaining]
        if kept:
            groups.append(kept)
            remaining = [name for name in remaining if name not in kept]
    if remaining:
        groups.append(remaining)
    return roc_weights(groups)


def _ratio(numerator: float, denominator: float) -> float:
    """Return ``numerator / denominator`` clamped to [0, 1]; 1 when there is no headroom."""
    if denominator <= 0.0:
        return 1.0
    return min(max(numerator / denominator, 0.0), 1.0)


def margin_and_shortfall(
    criterion: Criterion, value: float | None, threshold: float, window_h: float
) -> tuple[bool, float, float]:
    """Compare one site value with one threshold.

    Args:
        criterion: The criterion.
        value: Site value in the criterion's units; None counts as a full violation.
        threshold: Requirement value.
        window_h: Window length, hours.

    Returns:
        ``(met, margin, shortfall)``: margin in [0, 1] when met (else 0), shortfall in [0, 1]
        when violated (else 0), as defined in the module docstring.
    """
    lower, upper = criterion.bounds(window_h)
    if value is None:
        return False, 0.0, 1.0
    if criterion.kind == "min":
        if value >= threshold:
            return True, _ratio(value - threshold, upper - threshold), 0.0
        return False, 0.0, _ratio(threshold - value, threshold - lower)
    if value <= threshold:
        return True, _ratio(threshold - value, threshold - lower), 0.0
    return False, 0.0, _ratio(value - threshold, upper - threshold)


@dataclass(frozen=True)
class SiteResult:
    """The evaluated quantities of one site that the ranking needs.

    Attributes:
        site_id: Catalog id.
        metrics: Visibility metrics over the window.
        landing_slope_max_deg: Maximum slope over the landing-precision disk, degrees.
    """

    site_id: str
    metrics: VisibilityMetrics
    landing_slope_max_deg: float


def window_hours(window: TimeWindow) -> float:
    """Return the length of ``window`` in hours."""
    return (window.end_utc - window.start_utc).total_seconds() / 3600.0


def score_sites(
    requirements: MissionRequirements, results: Sequence[SiteResult], weights: Mapping[str, float]
) -> list[SiteScore]:
    """Score and order evaluated sites (pure function, no I/O).

    Args:
        requirements: Requirements with a window and at least one criterion.
        results: Evaluated sites, any order.
        weights: Criterion field -> weight, as from ``criterion_weights``.

    Returns:
        Site scores, best first, with 1-based ranks; ties broken by site id.

    Raises:
        ValueError: If the requirements have no window or no criterion.
    """
    if requirements.window is None:
        raise ValueError("ranking needs a time window")
    criteria = set_criteria(requirements)
    if not criteria:
        raise ValueError("set at least one constraint to rank sites")
    window_h = window_hours(requirements.window)
    rows: list[tuple[tuple[float, ...], SiteScore]] = []
    for site in results:
        met: dict[str, bool] = {}
        values: dict[str, float] = {}
        score = 0.0
        shortfall = 0.0
        for criterion in criteria:
            value = criterion.value(site.metrics, site.landing_slope_max_deg)
            threshold = float(getattr(requirements, criterion.field))
            ok, margin, short = margin_and_shortfall(criterion, value, threshold, window_h)
            met[criterion.field] = ok
            if value is not None:
                values[criterion.field] = value
            score += weights.get(criterion.field, 0.0) * margin
            shortfall += weights.get(criterion.field, 0.0) * short
        violations = sum(not ok for ok in met.values())
        passes = violations == 0
        key = (0.0, -score) if passes else (float(violations), shortfall)
        rows.append(
            (
                key,
                SiteScore(
                    site_id=site.site_id,
                    rank=1,
                    score=min(max(score, 0.0), 1.0) if passes else 0.0,
                    constraints_met=met,
                    criterion_values=values,
                    all_constraints_met=passes,
                    metrics=site.metrics,
                    landing_slope_max_deg=site.landing_slope_max_deg,
                ),
            )
        )
    rows.sort(key=lambda row: (row[0], row[1].site_id))
    return [row.model_copy(update={"rank": i}) for i, (_, row) in enumerate(rows, start=1)]


class CatalogRanker:
    """Ranks every catalog site in scope by evaluating it over the requested window.

    Attributes:
        catalog: Source of the candidate sites.
        evaluator: Evaluation engine (ephemeris plus terrain).
        archetypes: Archetypes by id, for the priority order behind the weights.
    """

    def __init__(
        self, catalog: SiteCatalog, evaluator: Evaluator, archetypes: Mapping[str, Archetype]
    ) -> None:
        """Store the collaborators.

        Args:
            catalog: Site catalog.
            evaluator: Site evaluator.
            archetypes: Archetypes by id (may be empty).
        """
        self.catalog = catalog
        self.evaluator = evaluator
        self.archetypes = archetypes

    def weights(self, requirements: MissionRequirements) -> dict[str, float]:
        """Return the criterion weights for ``requirements`` (archetype priority, if any)."""
        archetype = self.archetypes.get(requirements.archetype_id or "")
        priority = archetype.priority if archetype is not None else ()
        return criterion_weights([c.field for c in set_criteria(requirements)], priority)

    def rank(self, requirements: MissionRequirements) -> SiteRanking:
        """Rank the catalog sites in scope against ``requirements``.

        Args:
            requirements: Requirements with a window and at least one criterion.

        Returns:
            The ranking; sites whose evaluation failed are listed in ``unavailable``.

        Raises:
            ValueError: If the requirements have no window or no criterion.
        """
        if requirements.window is None:
            raise ValueError("ranking needs a time window")
        if not set_criteria(requirements):
            raise ValueError("set at least one constraint to rank sites")
        area = requirements.area or OperationsArea()
        results: list[SiteResult] = []
        unavailable: dict[str, str] = {}
        for site in self.catalog.list_sites():
            lat = site.location.lat_deg
            if requirements.latitude_min_deg is not None and lat < requirements.latitude_min_deg:
                continue
            if requirements.latitude_max_deg is not None and lat > requirements.latitude_max_deg:
                continue
            if requirements.origins is not None and site.origin not in requirements.origins:
                continue
            try:
                evaluation = self.evaluator.evaluate(
                    site.location, requirements.window, area, site.id
                )
            except Exception as error:  # one bad site must not hide the others
                logger.warning("ranking: %s not evaluated: %s", site.id, error)
                unavailable[site.id] = f"{type(error).__name__}: {error}"
                continue
            results.append(
                SiteResult(site.id, evaluation.metrics, evaluation.terrain.landing_slope_max_deg)
            )
        weights = self.weights(requirements)
        return SiteRanking(
            requirements=requirements,
            results=score_sites(requirements, results, weights),
            weights=weights,
            unavailable=unavailable,
        )


class Ranker(Protocol):
    """What the assistant needs from a ranker (structurally matches ``CatalogRanker``)."""

    def rank(self, requirements: MissionRequirements) -> SiteRanking:
        """Rank catalog sites; best first."""
        ...
