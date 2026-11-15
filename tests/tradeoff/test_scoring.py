# ABOUTME: Known-answer tests of the trade-off synthesis (TO-4) and sensitivity (TO-6)
# ABOUTME: Includes the spec acceptance case: 3 scenarios, fixed weights, expected scores and order

from pathlib import Path

import numpy as np
import pytest

from lunarnav.contracts import Evaluation
from lunarnav.tradeoff.engine import run_tradeoff
from lunarnav.tradeoff.foms import FomSpec, UserFomInput, computed_columns, user_columns
from lunarnav.tradeoff.scoring import Direction, normalize_column

EXAMPLES = Path(__file__).resolve().parents[2] / "data" / "examples"
HIGH, LOW = Direction.HIGHER, Direction.LOWER


def fom(fid: str, direction: Direction) -> FomSpec:
    return FomSpec(fid, fid, "", direction, "test")


def test_higher_is_better_shares_sum_to_one() -> None:
    assert np.allclose(normalize_column([0.6, 0.3, 0.1], HIGH), [0.6, 0.3, 0.1])
    assert np.allclose(normalize_column([2, 6], HIGH), [0.25, 0.75])


def test_lower_is_better_uses_the_normalized_complement() -> None:
    # sum = 600, n = 3: (600 - v) / 1200 -> 500/1200, 400/1200, 300/1200.
    shares = normalize_column([100, 200, 300], LOW)
    assert np.allclose(shares, [5 / 12, 4 / 12, 3 / 12]) and shares.sum() == pytest.approx(1)
    assert np.allclose(normalize_column([0, 50], LOW), [1.0, 0.0])  # zero darkness is best


def test_all_zero_values_share_equally_and_negatives_are_rejected() -> None:
    assert np.allclose(normalize_column([0, 0, 0], LOW), [1 / 3] * 3)
    with pytest.raises(ValueError, match=">= 0"):
        normalize_column([1, -1], HIGH)


def test_acceptance_three_scenarios_with_fixed_weights() -> None:
    # Spec TO-1..TO-4 acceptance. Sunlit share (higher): 0.6, 0.3, 0.1 -> shares 0.6, 0.3, 0.1.
    # Longest darkness (lower): 100, 200, 300 h -> 5/12, 4/12, 3/12. Weights 0.5 / 0.5:
    # A = 0.3 + 0.208333 = 0.508333, B = 0.15 + 0.166667 = 0.316667, C = 0.05 + 0.125 = 0.175.
    out = run_tradeoff(
        [(fom("light", HIGH), [0.6, 0.3, 0.1]), (fom("dark", LOW), [100, 200, 300])],
        direct_weights={"light": 1, "dark": 1},
    )
    assert np.allclose(out.scores, [0.508333, 0.316667, 0.175], atol=1e-6)
    assert out.ranking == [0, 1, 2] and out.scores.sum() == pytest.approx(1)
    assert out.weight_method == "direct" and out.consistency_ratio is None


def test_sensitivity_of_two_close_scenarios() -> None:
    # Shares: light A 0.6, B 0.4; dark (58 h vs 42 h, n = 2) A 0.42, B 0.58. Weights 0.5/0.5:
    # S_A = 0.51, S_B = 0.49. delta'(light) = 100 * 0.02 / 0.2 / 0.5 = 20 %;
    # delta'(dark) = 100 * 0.02 / 0.16 / 0.5 = 25 %. Light is the critical FoM (1/D = 5).
    out = run_tradeoff([(fom("light", HIGH), [0.6, 0.4]), (fom("dark", LOW), [58, 42])])
    assert np.allclose(out.scores, [0.51, 0.49])
    light, dark = out.sensitivity
    assert light.min_change_percent == pytest.approx(20.0)
    assert dark.min_change_percent == pytest.approx(25.0)
    assert light.sensitivity == pytest.approx(5.0)


def test_robust_ranking_has_no_feasible_weight_change() -> None:
    # The acceptance case: every delta' exceeds 100 % (e.g. light, A vs B: 0.191667/0.3/0.5).
    out = run_tradeoff([(fom("light", HIGH), [0.6, 0.3, 0.1]), (fom("dark", LOW), [100, 200, 300])])
    assert all(s.min_change_percent is None for s in out.sensitivity)


def test_default_judgments_are_equal_and_cite_their_source() -> None:
    out = run_tradeoff([(fom(f, HIGH), [1, 2]) for f in ("a", "b", "c")])
    assert out.weight_method == "default" and np.allclose(out.weights, 1 / 3)
    assert len(out.judgments) == 3 and all("Governale" in jd.source for jd in out.judgments)


def test_computed_foms_from_an_evaluation_payload() -> None:
    ev = Evaluation.model_validate_json((EXAMPLES / "evaluation.json").read_text())
    columns = computed_columns([ev, ev])
    ids = [spec.id for spec, _ in columns]
    assert ids[:5] == [
        "illumination_fraction",
        "longest_dark_h",
        "earth_visibility_fraction",
        "longest_earth_hidden_h",
        "landing_slope_max_deg",
    ]
    assert ("reachable_fraction" in ids) == (ev.terrain.reachable_fraction is not None)
    assert columns[1][1] == [ev.metrics.longest_dark_h] * 2
    assert "longest_dark_h" not in [s.id for s, _ in computed_columns([ev, ev], ["longest_dark_h"])]


def test_user_fom_enters_like_the_others_and_is_flagged() -> None:
    # Science interest 9, 5, 3 (higher) -> shares 9/17, 5/17, 3/17.
    user = user_columns([UserFomInput("Science interest", "1-9", HIGH, [9, 5, 3])], 3)
    spec, _ = user[0]
    assert spec.id == "user-1" and spec.user_supplied and spec.source == "user"
    out = run_tradeoff(
        [*user, (fom("light", HIGH), [1, 1, 1])], direct_weights={"user-1": 1, "light": 0}
    )
    assert np.allclose(out.scores, [9 / 17, 5 / 17, 3 / 17])
    with pytest.raises(ValueError, match="values"):
        user_columns([UserFomInput("x", "", HIGH, [1, 2])], 3)


def test_sensitivity_values_are_plain_floats() -> None:
    out = run_tradeoff([(fom("light", HIGH), [0.6, 0.4]), (fom("dark", LOW), [58, 42])])
    assert all(type(s.min_change_percent) is float for s in out.sensitivity)
