# ABOUTME: Contract-level tests of LunarTradeoff (D39): Evaluation in, TradeoffResult out, factory
# ABOUTME: Evaluations are the example payload with chosen metrics, so expected numbers are known

from pathlib import Path

import pytest

from lunarnav.contracts import (
    Evaluation,
    FomDirection,
    PairwiseJudgment,
    TradeoffResult,
    TradeoffSettings,
    UserFom,
)
from lunarnav.tradeoff import LunarTradeoff, build_tradeoff

EXAMPLES = Path(__file__).resolve().parents[2] / "data" / "examples"
OTHERS = [
    "earth_visibility_fraction",
    "longest_earth_hidden_h",
    "landing_slope_max_deg",
    "reachable_fraction",
]


def evaluation(light: float, dark_h: float) -> Evaluation:
    base = Evaluation.model_validate_json((EXAMPLES / "evaluation.json").read_text())
    metrics = base.metrics.model_copy(
        update={"illumination_fraction": light, "longest_dark_h": dark_h}
    )
    return base.model_copy(update={"metrics": metrics})


def three() -> list[Evaluation]:
    return [evaluation(0.6, 100.0), evaluation(0.3, 200.0), evaluation(0.1, 300.0)]


def test_acceptance_case_through_the_contract() -> None:
    settings = TradeoffSettings(
        labels=["A", "B", "C"],
        weights={"illumination_fraction": 1.0, "longest_dark_h": 1.0},
        excluded_foms=OTHERS,
    )
    result = LunarTradeoff().analyze(three(), settings)
    TradeoffResult.model_validate(result.model_dump())
    assert result.scores == pytest.approx([0.508333, 0.316667, 0.175], abs=1e-6)
    assert result.ranking == [0, 1, 2] and result.labels == ["A", "B", "C"]
    assert result.weights == pytest.approx({"illumination_fraction": 0.5, "longest_dark_h": 0.5})
    assert result.table[1]["longest_dark_h"].value == 200.0
    assert result.table[1]["longest_dark_h"].normalized == pytest.approx(4 / 12)
    assert "geometric means" in result.method


def test_judgments_drive_the_weights() -> None:
    settings = TradeoffSettings(
        labels=["A", "B", "C"],
        judgments=[
            PairwiseJudgment(a="illumination_fraction", b="longest_dark_h", value=3, source="user")
        ],
        excluded_foms=OTHERS,
    )
    result = LunarTradeoff().analyze(three(), settings)
    assert result.weight_method == "judgments" and result.consistency_ratio == 0.0
    assert result.weights["illumination_fraction"] == pytest.approx(0.75)


def test_default_weights_are_equal_over_all_applicable_foms() -> None:
    result = LunarTradeoff().analyze(three(), TradeoffSettings(labels=["A", "B", "C"]))
    assert result.weight_method == "default"
    assert list(result.weights.values()) == pytest.approx([1 / len(result.foms)] * len(result.foms))
    assert all("Governale" in j.source for j in result.judgments)


def test_user_fom_is_flagged_and_scored() -> None:
    settings = TradeoffSettings(
        labels=["A", "B", "C"],
        user_foms=[
            UserFom(
                name="Science interest", unit="1-9", direction=FomDirection.HIGHER, values=[9, 5, 3]
            )
        ],
        excluded_foms=[*OTHERS, "longest_dark_h"],
        weights={"illumination_fraction": 0.0, "user-1": 1.0},
    )
    result = LunarTradeoff().analyze(three(), settings)
    user = next(f for f in result.foms if f.id == "user-1")
    assert user.user_supplied and user.source == "user"
    assert result.scores == pytest.approx([9 / 17, 5 / 17, 3 / 17])


def test_mismatched_labels_and_unknown_judgments_are_rejected() -> None:
    with pytest.raises(ValueError, match="labels"):
        LunarTradeoff().analyze(three()[:2], TradeoffSettings(labels=["A", "B", "C"]))
    bad = TradeoffSettings(
        labels=["A", "B", "C"],
        judgments=[PairwiseJudgment(a="nope", b="longest_dark_h", value=2, source="user")],
    )
    with pytest.raises(ValueError, match="unknown"):
        LunarTradeoff().analyze(three(), bad)


def test_factory_builds_the_analyzer() -> None:
    assert isinstance(build_tradeoff(), LunarTradeoff)
