# ABOUTME: Trade-off engine: FoM columns -> AHP or direct weights -> table, scores, ranking
# ABOUTME: Module-internal result; converted to the contract models once they exist (D37)

"""Run one trade-off over the compared scenarios.

Weights come, in order of precedence, from direct weights, from the user's pairwise judgments, or
from the default judgments (all 1: Governale et al. 2021 has no criterion matching ours, so TO-2
gives equal importance). Scoring and sensitivity: ``lunarnav.tradeoff.scoring``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from lunarnav.tradeoff.ahp import MAX_CRITERIA, Judgment, ahp_weights, normalize_weights
from lunarnav.tradeoff.foms import FomSpec
from lunarnav.tradeoff.scoring import (
    Sensitivity,
    normalized_matrix,
    ranking,
    scores,
    sensitivity,
)

DEFAULT_JUDGMENT_SOURCE = (
    "Default: equal importance (Saaty 1). Governale et al. 2021 (doi:10.1007/s42401-021-00095-w) "
    "trades off micro-launchers; none of its criteria matches this FoM pair (spec TO-2)."
)
METHOD = (
    "AHP (Saaty 1-9 scale; weights = normalized row geometric means; CR = CI/RI <= 10%; "
    "Governale et al. 2021, sections 2.3-2.4). Per-FoM normalization summing to 1 over the "
    "scenarios: v/sum(v) for higher-is-better, (sum(v)-v)/((n-1) sum(v)) for lower-is-better "
    "(our adaptation). Score = sum of weight x normalized value. Sensitivity: minimum relative "
    "weight change swapping two scenarios, D_k (Triantaphyllou and Sanchez 1997; Governale et al. "
    "2021, section 2.5)."
)


@dataclass(frozen=True)
class TradeoffOutcome:
    """Result of one trade-off (module-internal).

    Attributes:
        foms: FoM columns, in order.
        values: Raw values, shape (scenarios, FoMs).
        normalized: Normalized values, same shape, each column sums to 1.
        weights: FoM weights, sum to 1, column order.
        weight_method: "default", "judgments" or "direct".
        judgments: Judgments used (with sources); empty for direct weights.
        consistency_ratio: Saaty CR of the judgments; None for direct weights.
        scores: Per scenario, sum to 1.
        ranking: Scenario indices, best first.
        sensitivity: Per FoM, column order.
    """

    foms: list[FomSpec]
    values: np.ndarray
    normalized: np.ndarray
    weights: np.ndarray
    weight_method: str
    judgments: list[Judgment]
    consistency_ratio: float | None
    scores: np.ndarray
    ranking: list[int]
    sensitivity: list[Sensitivity]


def default_judgments(ids: Sequence[str]) -> list[Judgment]:
    """Equal importance for every pair, each citing why (spec TO-2)."""
    return [
        Judgment(a, b, 1.0, DEFAULT_JUDGMENT_SOURCE)
        for k, a in enumerate(ids)
        for b in ids[k + 1 :]
    ]


def run_tradeoff(
    columns: Sequence[tuple[FomSpec, Sequence[float]]],
    judgments: Sequence[Judgment] | None = None,
    direct_weights: dict[str, float] | None = None,
) -> TradeoffOutcome:
    """Weights, normalized table, scores, ranking and sensitivity.

    Args:
        columns: (FoM, one value per scenario) pairs; all columns have the same length.
        judgments: User pairwise judgments; missing pairs default to 1. Ignored with weights.
        direct_weights: FoM id -> weight, normalized here; takes precedence over judgments.

    Returns:
        The outcome.

    Raises:
        ValueError: With fewer than 2 scenarios, no FoM, more than ``MAX_CRITERIA`` FoMs, ragged
            columns, or invalid values, judgments or weights.
    """
    if not columns:
        raise ValueError("no FoM to compare")
    if len(columns) > MAX_CRITERIA:
        raise ValueError(f"{len(columns)} FoMs: at most {MAX_CRITERIA}")
    foms = [spec for spec, _ in columns]
    ids = [f.id for f in foms]
    lengths = {len(v) for _, v in columns}
    if len(lengths) != 1 or lengths.pop() < 2:
        raise ValueError("every FoM needs one value per scenario, at least 2 scenarios")
    values = np.array([list(v) for _, v in columns], dtype=float).T
    normalized = normalized_matrix(values, [f.direction for f in foms])

    if direct_weights is not None:
        w = normalize_weights(direct_weights, ids)
        weights = np.array([w[i] for i in ids])
        method, used, cr = "direct", [], None
    else:
        used = list(judgments) if judgments else []
        given = {frozenset((j.a, j.b)) for j in used}
        method = "judgments" if used else "default"
        used += [j for j in default_judgments(ids) if frozenset((j.a, j.b)) not in given]
        ahp = ahp_weights(ids, used)
        weights, cr = ahp.weights, ahp.consistency_ratio

    score = scores(normalized, weights)
    return TradeoffOutcome(
        foms=foms,
        values=values,
        normalized=normalized,
        weights=weights,
        weight_method=method,
        judgments=used,
        consistency_ratio=cr,
        scores=score,
        ranking=ranking(list(score)),
        sensitivity=sensitivity(ids, normalized, weights, score),
    )
