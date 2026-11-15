# ABOUTME: Trade-off synthesis (TO-4): per-FoM normalization summing to 1, weighted sum, ranking
# ABOUTME: Sensitivity (TO-6): minimum relative weight change that swaps two scenarios (Dk)

"""Scores, ranking and weight sensitivity of the compared scenarios.

Synthesis (Governale et al. 2021, section 2.4): for every FoM the scenario values are normalized
so that they sum to 1 over the scenarios, then each scenario's score is the weighted sum of its
normalized values (scores also sum to 1).

* "higher is better": ``v_i / sum(v)``;
* "lower is better": ``(sum(v) - v_i) / ((n - 1) sum(v))``, the normalized complement. This is our
  adaptation (it also sums to 1, keeps the linear spacing of the values and accepts zeros, e.g.
  0 h of darkness); values must be >= 0. When every value is 0 the scenarios share 1/n.

Sensitivity (Triantaphyllou and Sanchez 1997, as summarized in Governale et al. 2021,
section 2.5): for FoM k and scenarios i, j, ``delta'_kij = 100 |S_j - S_i| / |n_jk - n_ik| / w_k``
is the minimum change of ``w_k``, in percent of ``w_k``, that makes the two scores equal. ``D_k``
is the smallest delta' not above 100 % (larger changes are not feasible) and ``1 / D_k`` the
sensitivity of the ranking to that FoM. Unlike the reference Excel template, which uses the raw
1-9 scores here, we use the normalized values that actually enter the score, since our raw values
carry units (hours, degrees).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

import numpy as np


class Direction(StrEnum):
    """Whether a larger FoM value is better or worse."""

    HIGHER = "higher"
    LOWER = "lower"


@dataclass(frozen=True)
class Sensitivity:
    """Weight sensitivity of one FoM.

    Attributes:
        fom_id: The FoM.
        min_change_percent: D_k, smallest feasible delta' in percent of the weight; None when no
            change up to 100 % swaps any pair.
        sensitivity: 1 / D_k (D_k in percent, as in the contract); None with D_k.
    """

    fom_id: str
    min_change_percent: float | None
    sensitivity: float | None


def normalize_column(values: Sequence[float], direction: Direction) -> np.ndarray:
    """Normalize one FoM over the scenarios so the shares sum to 1.

    Args:
        values: One value per scenario, >= 0.
        direction: Whether higher or lower values are better.

    Returns:
        The shares, same length, summing to 1.

    Raises:
        ValueError: If a value is negative or not finite.
    """
    v = np.asarray(values, dtype=float)
    if not np.all(np.isfinite(v)) or np.any(v < 0):
        raise ValueError(f"FoM values must be finite and >= 0, got {list(v)}")
    n, total = v.size, float(v.sum())
    if n == 1:
        return np.ones(1)
    if total == 0.0:
        return np.full(n, 1.0 / n)
    if direction is Direction.HIGHER:
        return v / total
    return (total - v) / ((n - 1) * total)


def normalized_matrix(values: np.ndarray, directions: Sequence[Direction]) -> np.ndarray:
    """Normalize every FoM column of a (scenarios x FoMs) matrix."""
    return np.column_stack([normalize_column(values[:, k], d) for k, d in enumerate(directions)])


def scores(normalized: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Weighted sums per scenario: ``normalized @ weights``."""
    return normalized @ weights


def ranking(score: Sequence[float]) -> list[int]:
    """Scenario indices, best first; ties keep the input order."""
    return sorted(range(len(score)), key=lambda i: (-score[i], i))


def sensitivity(
    fom_ids: Sequence[str], normalized: np.ndarray, weights: np.ndarray, score: np.ndarray
) -> list[Sensitivity]:
    """Criticality D_k and sensitivity 1/D_k of every FoM (see the module docstring).

    Args:
        fom_ids: FoM ids, in column order.
        normalized: Normalized values, shape (scenarios, FoMs).
        weights: FoM weights, sum to 1.
        score: Scenario scores.

    Returns:
        One entry per FoM, same order.
    """
    out = []
    n_alt = normalized.shape[0]
    for k, fom in enumerate(fom_ids):
        best = None
        for i in range(n_alt):
            for j in range(i + 1, n_alt):
                spread = abs(normalized[j, k] - normalized[i, k])
                if spread == 0.0 or weights[k] == 0.0:
                    continue
                delta = float(100.0 * abs(score[j] - score[i]) / spread / weights[k])
                if 0.0 < delta <= 100.0 and (best is None or delta < best):
                    best = delta
        out.append(Sensitivity(fom, best, None if best is None else 1.0 / best))
    return out
