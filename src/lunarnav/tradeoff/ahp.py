# ABOUTME: AHP weights (TO-2): reciprocal pairwise matrix, row geometric-mean weights, consistency
# ABOUTME: Saaty 1-9 scale; CR = CI / RI with Saaty's random index; CR <= 10 % is acceptable

"""Analytic Hierarchy Process weights for the trade-off (spec TO-2, decision D6).

Judgments use Saaty's 1-9 scale (Governale et al. 2021, Table 1): ``a_ij`` says how much more
important criterion i is than j, and ``a_ji = 1 / a_ij``. Weights are the normalized row
geometric means of the matrix, the standard AHP approximation of the principal eigenvector (it is
exact for consistent matrices, always for 2 x 2) and the method of the team's reference Excel
template, so the exported workbook computes the same numbers with plain formulas.

Consistency (Saaty): ``lambda_max`` is the mean of ``(A w)_i / w_i``, ``CI = (lambda_max - n) /
(n - 1)`` and ``CR = CI / RI(n)``; judgments are acceptably consistent when ``CR <= 0.10``
(Governale et al. 2021, section 2.3).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np

# Saaty's random consistency index RI(n) for n = 1..9 (T. L. Saaty, The Analytic Hierarchy
# Process, 1980), as used by the team's reference AHP template. n > 9 is not supported.
SAATY_RI = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45}
MAX_CRITERIA = max(SAATY_RI)
CR_THRESHOLD = 0.10  # Governale et al. 2021, section 2.3
SAATY_MIN, SAATY_MAX = 1.0 / 9.0, 9.0


@dataclass(frozen=True)
class Judgment:
    """One pairwise judgment: criterion ``a`` is ``value`` times as important as ``b``."""

    a: str
    b: str
    value: float
    source: str


@dataclass(frozen=True)
class AhpWeights:
    """Weights and consistency of one pairwise comparison matrix.

    Attributes:
        ids: Criteria, in matrix order.
        matrix: Reciprocal pairwise matrix, shape (n, n).
        weights: Normalized row geometric means, sum to 1.
        lambda_max: Mean of (A w) / w.
        consistency_index: (lambda_max - n) / (n - 1); 0 for n <= 2.
        consistency_ratio: CI / RI(n); 0 for n <= 2.
    """

    ids: list[str]
    matrix: np.ndarray
    weights: np.ndarray
    lambda_max: float
    consistency_index: float
    consistency_ratio: float

    @property
    def consistent(self) -> bool:
        """True when CR <= 10 %."""
        return self.consistency_ratio <= CR_THRESHOLD + 1e-12

    def as_dict(self) -> dict[str, float]:
        """Criterion id -> weight."""
        return {i: float(w) for i, w in zip(self.ids, self.weights, strict=True)}


def pairwise_matrix(ids: Sequence[str], judgments: Iterable[Judgment]) -> np.ndarray:
    """Reciprocal matrix from judgments; pairs without a judgment default to 1 (equal).

    Args:
        ids: Criteria, in matrix order.
        judgments: Judgments on pairs of ``ids``, at most one per unordered pair.

    Returns:
        The matrix, shape (n, n), ones on the diagonal.

    Raises:
        ValueError: On an unknown id, a self-comparison, a value outside the Saaty scale, a
            repeated pair, or more criteria than ``MAX_CRITERIA``.
    """
    n = len(ids)
    if not 1 <= n <= MAX_CRITERIA:
        raise ValueError(f"{n} criteria: AHP needs 1 to {MAX_CRITERIA}")
    index = {c: k for k, c in enumerate(ids)}
    a = np.ones((n, n))
    seen: set[frozenset[str]] = set()
    for j in judgments:
        if j.a not in index or j.b not in index:
            raise ValueError(f"judgment {j.a} vs {j.b}: unknown criterion")
        if j.a == j.b:
            raise ValueError(f"judgment compares {j.a} with itself")
        if not SAATY_MIN - 1e-12 <= j.value <= SAATY_MAX + 1e-12:
            raise ValueError(f"judgment {j.a} vs {j.b} = {j.value}: outside Saaty's 1/9..9")
        pair = frozenset((j.a, j.b))
        if pair in seen:
            raise ValueError(f"pair {j.a} / {j.b} judged twice")
        seen.add(pair)
        a[index[j.a], index[j.b]] = j.value
        a[index[j.b], index[j.a]] = 1.0 / j.value
    return a


def ahp_weights(ids: Sequence[str], judgments: Iterable[Judgment] = ()) -> AhpWeights:
    """Row geometric-mean weights and Saaty consistency of the judgments.

    Args:
        ids: Criteria, in matrix order.
        judgments: Pairwise judgments; missing pairs count as equal importance.

    Returns:
        The weights and consistency measures.
    """
    a = pairwise_matrix(ids, judgments)
    n = len(ids)
    geo = np.exp(np.log(a).mean(axis=1))
    w = geo / geo.sum()
    lam = float(np.mean((a @ w) / w))
    ci = (lam - n) / (n - 1) if n > 2 else 0.0
    ri = SAATY_RI[n]
    cr = ci / ri if ri > 0 else 0.0
    return AhpWeights(list(ids), a, w, lam, float(ci), float(cr))


def normalize_weights(weights: dict[str, float], ids: Sequence[str]) -> dict[str, float]:
    """Direct weights restricted to ``ids`` and scaled to sum to 1.

    Raises:
        ValueError: On a negative weight, a missing id, or weights summing to 0.
    """
    missing = [i for i in ids if i not in weights]
    if missing:
        raise ValueError(f"no weight for {missing}")
    if any(weights[i] < 0 for i in ids):
        raise ValueError("weights must be >= 0")
    total = sum(weights[i] for i in ids)
    if total <= 0:
        raise ValueError("weights sum to 0")
    return {i: weights[i] / total for i in ids}
