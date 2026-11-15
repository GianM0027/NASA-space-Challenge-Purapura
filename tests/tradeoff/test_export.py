# ABOUTME: Tests of the live Excel export (TO-4): the workbook's formulas, re-evaluated in Python,
# ABOUTME: reproduce the app's weights, CR, scores, ranks and D_k; edited inputs recompute correctly

import warnings
from pathlib import Path

import pytest
from openpyxl import load_workbook

from lunarnav.contracts import FomDirection, PairwiseJudgment, TradeoffSettings, UserFom
from lunarnav.tradeoff import LunarTradeoff
from lunarnav.tradeoff.export import DEC_ROW, FIRST, FOM_ROW, _Refs, col

with warnings.catch_warnings():
    warnings.simplefilter("ignore", SyntaxWarning)  # the formulas package ships old literals
    import formulas

from tests.tradeoff.test_analyzer import OTHERS, three

JUDGED = TradeoffSettings(
    labels=["A", "B", "C"],
    excluded_foms=OTHERS,
    user_foms=[
        UserFom(name="Science", unit="1-9", direction=FomDirection.HIGHER, values=[3, 5, 9])
    ],
    judgments=[
        PairwiseJudgment(a="illumination_fraction", b="longest_dark_h", value=3, source="user"),
        PairwiseJudgment(a="illumination_fraction", b="user-1", value=5, source="user"),
        PairwiseJudgment(a="longest_dark_h", b="user-1", value=3, source="user"),
    ],
)


def evaluate_workbook(path: Path):
    """Recalculate every formula of the saved workbook; return a cell getter."""
    model = formulas.ExcelModel().loads(str(path)).finish()
    solution = model.calculate()

    def get(sheet: str, cell: str):
        return solution[f"'[{path.name}]{sheet.upper()}'!{cell}"].value[0][0]

    return get


def export(tmp_path: Path, settings: TradeoffSettings):
    analyzer = LunarTradeoff()
    result = analyzer.analyze(three(), settings)
    result = result.model_copy(update={"ai_comment": "A leads on sunlit time (0.6)."})
    path = tmp_path / "tradeoff.xlsx"
    path.write_bytes(analyzer.export_xlsx(result, three()))
    return result, path


def check_against_result(get, result, refs: _Refs) -> None:
    for k, fom in enumerate(result.foms):
        weight = get("2. AHP", f"{col(refs.weight_col)}{FOM_ROW + k}")
        assert float(weight) == pytest.approx(result.weights[fom.id], abs=1e-9)
    for s in range(refs.m):
        score = get("4. Decision", f"{col(FIRST + 1 + s)}{refs.final_row}")
        rank = get("4. Decision", f"{col(FIRST + 1 + s)}{refs.rank_row}")
        assert float(score) == pytest.approx(result.scores[s], abs=1e-9)
        assert int(rank) == result.ranking.index(s) + 1
    dk_col = col(FIRST + 1 + refs.m * (refs.m - 1) // 2)
    for k, sens in enumerate(result.sensitivity):
        dk = get("5. Sensitivity", f"{dk_col}{DEC_ROW + k}")
        if sens.min_change_percent is None:
            assert dk == ""
        else:
            assert float(dk) == pytest.approx(sens.min_change_percent, abs=1e-9)


def test_reopened_workbook_reproduces_the_app_numbers(tmp_path: Path) -> None:
    result, path = export(tmp_path, JUDGED)
    refs = _Refs(len(result.foms), len(result.labels))
    get = evaluate_workbook(path)
    check_against_result(get, result, refs)
    assert float(get("2. AHP", f"F{refs.res_row}")) == pytest.approx(result.consistency_ratio)
    assert get("2. AHP", f"G{refs.res_row}") == "YES"
    assert get("6. Recommendation", "C5") == "A"
    assert get("6. Recommendation", "C10") == "Sunlit time"  # D_k 97.6 %, the only feasible one


def test_direct_weights_mode_is_exported(tmp_path: Path) -> None:
    settings = TradeoffSettings(
        labels=["A", "B", "C"],
        excluded_foms=OTHERS,
        weights={"illumination_fraction": 1, "longest_dark_h": 1},
    )
    result, path = export(tmp_path, settings)
    assert load_workbook(path)["2. AHP"]["C4"].value == "DIRECT"
    check_against_result(evaluate_workbook(path), result, _Refs(2, 3))
    assert result.scores == pytest.approx([0.508333, 0.316667, 0.175], abs=1e-6)  # acceptance


def test_editing_an_input_recomputes_the_trade_off(tmp_path: Path) -> None:
    # Switch the user FoM off in the workbook: the remaining weights must equal a fresh app run
    # with that FoM excluded (geometric means over the active 2 x 2 block).
    _, path = export(tmp_path, JUDGED)
    wb = load_workbook(path)
    wb["1. FoM"][f"B{FOM_ROW + 2}"] = "NO"
    edited = tmp_path / "edited.xlsx"
    wb.save(edited)
    get = evaluate_workbook(edited)
    expected = LunarTradeoff().analyze(
        three(),
        TradeoffSettings(
            labels=["A", "B", "C"],
            excluded_foms=OTHERS,
            judgments=[JUDGED.judgments[0]],
        ),
    )
    refs = _Refs(3, 3)
    w0 = float(get("2. AHP", f"{col(refs.weight_col)}{FOM_ROW}"))
    assert w0 == pytest.approx(expected.weights["illumination_fraction"])
    for s in range(3):
        score = float(get("4. Decision", f"{col(FIRST + 1 + s)}{refs.final_row}"))
        assert score == pytest.approx(expected.scores[s])


def test_workbook_content_for_readers(tmp_path: Path) -> None:
    _, path = export(tmp_path, JUDGED)
    wb = load_workbook(path)
    assert wb.sheetnames == [
        "0. Instructions",
        "1. FoM",
        "2. AHP",
        "3. Scoring",
        "4. Decision",
        "5. Sensitivity",
        "6. Recommendation",
        "7. Data & sources",
    ]
    fom = wb["1. FoM"]
    assert fom[f"D{FOM_ROW + 2}"].value == "Science" and fom[f"H{FOM_ROW + 2}"].value == "YES"
    assert wb["3. Scoring"][f"C{FOM_ROW + 1}"].value == 100.0  # raw longest darkness, A
    rec = wb["6. Recommendation"]
    assert rec["C11"].value == "A leads on sunlit time (0.6)." and "Governale" in rec["C12"].value
    assert wb["7. Data & sources"]["N6"].value == three()[0].terrain.dem_source
