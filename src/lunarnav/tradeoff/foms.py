# ABOUTME: Figures of merit (TO-1): six computed FoMs read from Evaluation, plus user FoMs (TO-3)
# ABOUTME: Each FoM has an id, unit, direction and source; redundant metrics are left out on purpose

"""Figures of merit of the trade-off.

Six computed FoMs, read from ``Evaluation`` only (spec TO-1). Left out on purpose, because they are
redundant with or derived from these (AHP criteria should be independent): longest continuous
light, mean Sun and Earth elevations, joint Sun and Earth visibility.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from lunarnav.contracts import Evaluation
from lunarnav.tradeoff.scoring import Direction


@dataclass(frozen=True)
class FomSpec:
    """Definition of one FoM column.

    Attributes:
        id: Stable id (e.g. "longest_dark_h", "user-1").
        name: Display name.
        unit: Unit text ("" for fractions).
        direction: Whether higher or lower values are better.
        source: Where the values come from ("Evaluation.metrics.longest_dark_h" or "user").
        user_supplied: True for FoMs entered by the user (TO-3).
    """

    id: str
    name: str
    unit: str
    direction: Direction
    source: str
    user_supplied: bool = False


@dataclass(frozen=True)
class _Computed:
    spec: FomSpec
    read: Callable[[Evaluation], float | None]


COMPUTED: tuple[_Computed, ...] = (
    _Computed(
        FomSpec(
            "illumination_fraction",
            "Sunlit time",
            "",
            Direction.HIGHER,
            "Evaluation.metrics.illumination_fraction",
        ),
        lambda e: e.metrics.illumination_fraction,
    ),
    _Computed(
        FomSpec(
            "longest_dark_h",
            "Longest darkness",
            "h",
            Direction.LOWER,
            "Evaluation.metrics.longest_dark_h",
        ),
        lambda e: e.metrics.longest_dark_h,
    ),
    _Computed(
        FomSpec(
            "earth_visibility_fraction",
            "Earth in view",
            "",
            Direction.HIGHER,
            "Evaluation.metrics.earth_visibility_fraction",
        ),
        lambda e: e.metrics.earth_visibility_fraction,
    ),
    _Computed(
        FomSpec(
            "longest_earth_hidden_h",
            "Longest Earth outage",
            "h",
            Direction.LOWER,
            "Evaluation.metrics.longest_earth_hidden_h",
        ),
        lambda e: e.metrics.longest_earth_hidden_h,
    ),
    _Computed(
        FomSpec(
            "landing_slope_max_deg",
            "Landing slope (P99, 100 m)",
            "deg",
            Direction.LOWER,
            "Evaluation.terrain.landing_slope_max_deg",
        ),
        lambda e: e.terrain.landing_slope_max_deg,
    ),
    _Computed(
        FomSpec(
            "reachable_fraction",
            "Reachable area",
            "",
            Direction.HIGHER,
            "Evaluation.terrain.reachable_fraction",
        ),
        lambda e: e.terrain.reachable_fraction,
    ),
)


@dataclass(frozen=True)
class UserFomInput:
    """A FoM entered by the user (TO-3): one value per scenario, same order."""

    name: str
    unit: str
    direction: Direction
    values: Sequence[float]


def computed_columns(
    evaluations: Sequence[Evaluation], excluded: Sequence[str] = ()
) -> list[tuple[FomSpec, list[float]]]:
    """The computed FoMs that apply to every scenario, with their values.

    A FoM is skipped when it is excluded by the user or missing for some scenario (e.g. the
    reachable share without an operating range).
    """
    columns = []
    for fom in COMPUTED:
        if fom.spec.id in excluded:
            continue
        values = [fom.read(e) for e in evaluations]
        if any(v is None for v in values):
            continue
        columns.append((fom.spec, [float(v) for v in values]))
    return columns


def user_columns(
    user_foms: Sequence[UserFomInput], n_scenarios: int, excluded: Sequence[str] = ()
) -> list[tuple[FomSpec, list[float]]]:
    """User FoMs as columns, ids ``user-1``, ``user-2``... in input order.

    Raises:
        ValueError: If a user FoM does not have exactly one value per scenario.
    """
    columns = []
    for k, u in enumerate(user_foms, start=1):
        if len(u.values) != n_scenarios:
            raise ValueError(
                f"user FoM {u.name!r}: {len(u.values)} values, {n_scenarios} scenarios"
            )
        spec = FomSpec(f"user-{k}", u.name, u.unit, u.direction, "user", user_supplied=True)
        if spec.id not in excluded:
            columns.append((spec, [float(v) for v in u.values]))
    return columns
