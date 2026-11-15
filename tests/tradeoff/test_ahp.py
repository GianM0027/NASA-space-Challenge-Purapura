# ABOUTME: Known-answer tests of the AHP weights (TO-2): geometric mean, lambda max, CR, validation
# ABOUTME: Expected values computed by hand from Saaty's definitions

import numpy as np
import pytest

from lunarnav.tradeoff.ahp import Judgment, ahp_weights, normalize_weights, pairwise_matrix


def j(a: str, b: str, value: float) -> Judgment:
    return Judgment(a, b, value, "test")


def test_no_judgment_means_equal_weights_and_zero_cr() -> None:
    w = ahp_weights(["a", "b", "c", "d"])
    assert np.allclose(w.weights, 0.25)
    assert w.lambda_max == pytest.approx(4.0) and w.consistency_ratio == pytest.approx(0.0)


def test_consistent_matrix_returns_the_generating_weights() -> None:
    # a_ij = w_i / w_j with w = (0.5, 0.3, 0.2): geometric means recover w exactly, lambda_max = n.
    judgments = [j("a", "b", 0.5 / 0.3), j("a", "c", 0.5 / 0.2), j("b", "c", 0.3 / 0.2)]
    w = ahp_weights(["a", "b", "c"], judgments)
    assert np.allclose(w.weights, [0.5, 0.3, 0.2])
    assert w.lambda_max == pytest.approx(3.0) and w.consistency_ratio == pytest.approx(0.0)


def test_slightly_inconsistent_matrix_by_hand() -> None:
    # A = [[1, 3, 5], [1/3, 1, 3], [1/5, 1/3, 1]]. Row geometric means: 15^(1/3) = 2.4662, 1,
    # (1/15)^(1/3) = 0.4055; sum 3.8717 -> w = (0.6370, 0.2583, 0.1047). A.w / w = 3.0385 for
    # every row, so CI = 0.0193 and CR = CI / 0.58 = 0.0332: consistent (< 10 %).
    w = ahp_weights(["a", "b", "c"], [j("a", "b", 3), j("a", "c", 5), j("b", "c", 3)])
    assert np.allclose(w.weights, [0.6370, 0.2583, 0.1047], atol=1e-4)
    assert w.lambda_max == pytest.approx(3.0385, abs=1e-4)
    assert w.consistency_ratio == pytest.approx(0.0332, abs=1e-4) and w.consistent


def test_strongly_inconsistent_judgments_fail_the_10_percent_rule() -> None:
    # a > b (9), b > c (9) but c > a (9): circular preferences.
    w = ahp_weights(["a", "b", "c"], [j("a", "b", 9), j("b", "c", 9), j("c", "a", 9)])
    assert w.consistency_ratio > 0.10 and not w.consistent


def test_two_criteria_are_always_consistent() -> None:
    w = ahp_weights(["a", "b"], [j("a", "b", 4)])
    assert np.allclose(w.weights, [0.8, 0.2]) and w.consistency_ratio == 0.0


def test_reciprocal_is_filled_in() -> None:
    a = pairwise_matrix(["a", "b"], [j("b", "a", 5)])
    assert a[1, 0] == 5 and a[0, 1] == pytest.approx(0.2)


@pytest.mark.parametrize(
    ("judgments", "message"),
    [
        ([j("a", "x", 2)], "unknown"),
        ([j("a", "a", 2)], "itself"),
        ([j("a", "b", 10)], "Saaty"),
        ([j("a", "b", 2), j("b", "a", 3)], "twice"),
    ],
)
def test_invalid_judgments_are_rejected(judgments: list[Judgment], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        pairwise_matrix(["a", "b"], judgments)


def test_more_than_nine_criteria_are_rejected() -> None:
    with pytest.raises(ValueError, match="1 to 9"):
        ahp_weights([str(k) for k in range(10)])


def test_direct_weights_are_normalized() -> None:
    assert normalize_weights({"a": 2, "b": 6, "x": 9}, ["a", "b"]) == {"a": 0.25, "b": 0.75}
    with pytest.raises(ValueError, match="no weight"):
        normalize_weights({"a": 1}, ["a", "b"])
