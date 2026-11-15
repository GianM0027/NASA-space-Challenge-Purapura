# ABOUTME: Live Excel export of a trade-off (TO-4): template sheet layout, formulas, editable inputs
# ABOUTME: Pre-filled from TradeoffResult; recomputes weights, CR, scores, rank and D_k in Excel

"""Write a trade-off as a live Excel workbook (spec TO-4, decision D39).

The layout follows the team's reference AHP template (sheets 0 to 6, same palette). Yellow cells
are inputs pre-filled from the app (FoM activity and direction, pairwise judgments, weight mode
and direct weights, raw values); every other number is a formula, so editing an input recomputes
weights, consistency, normalized values, scores, ranking and sensitivity exactly as the app does
(``lunarnav.tradeoff.engine``). Differences from the template, on purpose:

* raw values in their units instead of 1-9 scores, with a direction column and the normalized
  complement for lower-is-better FoMs;
* geometric means and A.w use helper cells (no array formulas, no "@" fix needed);
* sensitivity uses normalized values (see ``lunarnav.tradeoff.scoring``) and 1 / D_k (D39);
* a weight-mode cell (AHP or DIRECT) and a "7. Data & sources" sheet.
"""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from lunarnav.contracts import Evaluation, TradeoffResult
from lunarnav.tradeoff.ahp import CR_THRESHOLD, SAATY_RI

# Palette of the reference template.
TEAL_DARK, TEAL_MID, TEAL_PALE, NAVY = "1A6B78", "2A8FA0", "EAF5F7", "1F3864"
WHITE, INPUT_BG, AMBER, GREY = "FFFFFF", "FFFBE6", "C9A227", "E2ECF0"

FOM_ROW = 7  # first FoM row on sheets 1 to 3
DEC_ROW = 6  # first FoM row on sheets 4 and 5
FIRST = 3  # first data column (C)


def col(c: int) -> str:
    """Column letter of a 1-based index."""
    return get_column_letter(c)


def _style(cell, *, bold=False, fg="1F1F1F", bg=None, inp=False, fmt=None, wrap=False) -> None:
    cell.font = Font(name="Calibri", size=10, bold=bold, color=fg)
    if inp:
        bg = INPUT_BG
        side = Side(style="thin", color=AMBER)
        cell.border = Border(left=side, right=side, top=side, bottom=side)
    if bg:
        cell.fill = PatternFill("solid", fgColor=bg)
    cell.alignment = Alignment(vertical="center", wrap_text=wrap)
    if fmt:
        cell.number_format = fmt


def _header(ws: Worksheet, row: int, column: int, text: str) -> None:
    cell = ws.cell(row, column, text)
    _style(cell, bold=True, fg=WHITE, bg=TEAL_DARK, wrap=True)


def _title(ws: Worksheet, text: str, sub: str = "") -> None:
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 3
    cell = ws.cell(2, 2, text)
    cell.font = Font(name="Calibri", size=16, bold=True, color=WHITE)
    cell.fill = PatternFill("solid", fgColor=TEAL_DARK)
    if sub:
        note = ws.cell(3, 2, sub)
        note.font = Font(name="Calibri", size=9, italic=True, color=NAVY)


class _Refs:
    """Cell references shared across sheets for n FoMs and m scenarios."""

    def __init__(self, n: int, m: int):
        self.n, self.m = n, m
        last = FOM_ROW + n - 1
        self.active_range = f"'1. FoM'!$B${FOM_ROW}:$B${last}"
        self.n_active = f'COUNTIF({self.active_range},"YES")'
        # 2. AHP columns
        self.geo_col = FIRST + n
        self.ahp_w_col = FIRST + n + 1
        self.direct_col = FIRST + n + 2
        self.weight_col = FIRST + n + 3
        self.mask_row = FOM_ROW + n + 3  # active-masked matrix
        self.wrow = self.mask_row + n + 1  # transposed AHP weights
        self.aw_row = self.wrow + 1
        self.lam_row = self.aw_row + 1
        self.res_row = self.lam_row + 3
        self.ri_row = self.res_row + 3
        # 3. Scoring columns
        self.sum_col = FIRST + m
        self.norm_col = FIRST + m + 2
        # 4. Decision rows
        self.final_row = DEC_ROW + n
        self.rank_row = self.final_row + 1

    def active(self, k: int) -> str:
        return f"'1. FoM'!$B${FOM_ROW + k}"

    def direction(self, k: int) -> str:
        return f"'1. FoM'!$F${FOM_ROW + k}"

    def name(self, k: int) -> str:
        return f"'1. FoM'!$D${FOM_ROW + k}"

    def weight(self, k: int) -> str:
        return f"'2. AHP'!${col(self.weight_col)}${FOM_ROW + k}"

    def norm(self, k: int, s: int) -> str:
        return f"'3. Scoring'!${col(self.norm_col + s)}${FOM_ROW + k}"

    def score(self, s: int) -> str:
        return f"'4. Decision'!${col(FIRST + 1 + s)}${self.final_row}"

    @property
    def scores_range(self) -> str:
        return (
            f"'4. Decision'!${col(FIRST + 1)}${self.final_row}:"
            f"${col(FIRST + self.m)}${self.final_row}"
        )

    @property
    def labels_range(self) -> str:
        return f"'3. Scoring'!${col(FIRST)}$6:${col(FIRST + self.m - 1)}$6"

    @property
    def cr(self) -> str:
        return f"'2. AHP'!$F${self.res_row}"


def build_workbook(result: TradeoffResult, evaluations: list[Evaluation]) -> Workbook:
    """The live workbook for one trade-off (see the module docstring).

    Args:
        result: The trade-off, AI comment included if any.
        evaluations: The evaluations behind it, one per scenario, for the data sheet.

    Returns:
        The workbook (not yet saved).
    """
    n, m = len(result.foms), len(result.labels)
    r = _Refs(n, m)
    wb = Workbook()
    _instructions(wb.active)
    _fom_sheet(wb.create_sheet("1. FoM"), result)
    _ahp_sheet(wb.create_sheet("2. AHP"), result, r)
    _scoring_sheet(wb.create_sheet("3. Scoring"), result, r)
    _decision_sheet(wb.create_sheet("4. Decision"), result, r)
    _sensitivity_sheet(wb.create_sheet("5. Sensitivity"), r)
    _recommendation_sheet(wb.create_sheet("6. Recommendation"), result, r)
    _sources_sheet(wb.create_sheet("7. Data & sources"), result, evaluations)
    return wb


def export_xlsx(result: TradeoffResult, evaluations: list[Evaluation]) -> bytes:
    """The live workbook as .xlsx bytes."""
    buffer = BytesIO()
    build_workbook(result, evaluations).save(buffer)
    return buffer.getvalue()


def _instructions(ws: Worksheet) -> None:
    ws.title = "0. Instructions"
    _title(ws, "TRADE-OFF ANALYSIS - AHP / SAATY", "LunarNav export: live formulas, yellow = input")
    ws.column_dimensions["B"].width = 110
    steps = [
        "1. FoM: Active = YES/NO includes or excludes a FoM; "
        "Direction = higher or lower is better.",
        "2. AHP: fill the upper triangle (Saaty 1-9 and reciprocals); "
        "the lower triangle is 1/a_ij. Weights = normalized row geometric means. "
        "Weight mode AHP uses them; DIRECT uses the direct-weight column "
        "(normalized over active FoMs). CR = CI / RI(n), acceptable <= 10%.",
        "3. Scoring: raw values in the FoM unit. Normalized: v / sum for higher-is-better, "
        "(sum - v) / ((n - 1) sum) for lower-is-better; each FoM sums to 1 over the scenarios.",
        "4. Decision: weighted normalized values, final score and rank (1 = best).",
        "5. Sensitivity: delta' = 100 |S_j - S_i| / |n_jk - n_ik| / w_k for every pair; "
        "D_k = smallest feasible delta' (<= 100%); sensitivity = 1 / D_k. "
        "Small D_k = critical FoM.",
        "6. Recommendation: winner, margin, consistency and the AI comment "
        "(numbers from the table).",
        "7. Data & sources: windows, areas and data products behind every computed value.",
        "Sources: Saaty (1980); Governale et al. 2021, Aerospace Systems, "
        "doi:10.1007/s42401-021-00095-w (method, sections 2.3-2.5); "
        "Triantaphyllou and Sanchez 1997.",
    ]
    for k, text in enumerate(steps):
        cell = ws.cell(5 + k, 2, text)
        _style(cell, bg=TEAL_PALE, fg=NAVY, wrap=True)
        ws.row_dimensions[5 + k].height = 32


def _fom_sheet(ws: Worksheet, result: TradeoffResult) -> None:
    _title(
        ws, "FIGURES OF MERIT", "Active and Direction are inputs; user-supplied FoMs are flagged"
    )
    for c, (text, width) in enumerate(
        [
            ("Active?", 9),
            ("#", 5),
            ("Figure of merit", 30),
            ("Unit", 10),
            ("Direction", 11),
            ("Source", 42),
            ("User-supplied", 13),
        ],
        start=2,
    ):
        _header(ws, 6, c, text)
        ws.column_dimensions[col(c)].width = width
    for k, f in enumerate(result.foms):
        row = FOM_ROW + k
        _style(ws.cell(row, 2, "YES"), inp=True, bold=True)
        ws.cell(row, 3, k + 1)
        ws.cell(row, 4, f.name)
        ws.cell(row, 5, f.unit)
        _style(ws.cell(row, 6, f.direction.value), inp=True)
        ws.cell(row, 7, f.source)
        ws.cell(row, 8, "YES" if f.user_supplied else "NO")


def _ahp_sheet(ws: Worksheet, result: TradeoffResult, r: _Refs) -> None:
    n = r.n
    ids = [f.id for f in result.foms]
    _title(
        ws,
        "AHP - PAIRWISE MATRIX, WEIGHTS, CONSISTENCY",
        "Fill the upper triangle (yellow). Weight mode: AHP or DIRECT",
    )
    ws.cell(4, 2, "Weight mode")
    mode = "DIRECT" if result.weight_method == "direct" else "AHP"
    _style(ws.cell(4, 3, mode), inp=True, bold=True)
    ws.column_dimensions["B"].width = 30
    _header(ws, 6, 2, "FoM \\ FoM")
    judged = {(j.a, j.b): j.value for j in result.judgments}
    for j in range(n):
        ws.cell(6, FIRST + j, f"={r.name(j)}")
        _style(ws.cell(6, FIRST + j), bold=True, fg=WHITE, bg=TEAL_DARK, wrap=True)
        ws.column_dimensions[col(FIRST + j)].width = 12
    for c, text in [
        (r.geo_col, "Geom. mean"),
        (r.ahp_w_col, "AHP weight"),
        (r.direct_col, "Direct weight"),
        (r.weight_col, "Weight used"),
    ]:
        _header(ws, 6, c, text)
        ws.column_dimensions[col(c)].width = 13

    for i in range(n):
        row = FOM_ROW + i
        ws.cell(row, 2, f"={r.name(i)}")
        for j in range(n):
            cell = ws.cell(row, FIRST + j)
            if i == j:
                cell.value = 1
            elif j > i:
                value = judged.get((ids[i], ids[j]))
                if value is None:
                    back = judged.get((ids[j], ids[i]))
                    value = 1.0 / back if back else 1.0
                cell.value = value
                _style(cell, inp=True, fmt="0.000")
            else:
                cell.value = f"=1/{col(FIRST + i)}{FOM_ROW + j}"
                _style(cell, bg=GREY, fmt="0.000")
        mask = f"{col(FIRST)}{r.mask_row + i}:{col(FIRST + n - 1)}{r.mask_row + i}"
        ws.cell(row, r.geo_col, f'=IF({r.active(i)}="YES",PRODUCT({mask})^(1/{r.n_active}),"")')
        geo_range = f"${col(r.geo_col)}${FOM_ROW}:${col(r.geo_col)}${FOM_ROW + n - 1}"
        ws.cell(
            row, r.ahp_w_col, f'=IF({r.active(i)}="YES",{col(r.geo_col)}{row}/SUM({geo_range}),"")'
        )
        _style(ws.cell(row, r.direct_col, float(result.weights[ids[i]])), inp=True, fmt="0.0000")
        direct_range = f"${col(r.direct_col)}${FOM_ROW}:${col(r.direct_col)}${FOM_ROW + n - 1}"
        ws.cell(
            row,
            r.weight_col,
            f'=IF({r.active(i)}<>"YES",0,IF($C$4="DIRECT",'
            f'{col(r.direct_col)}{row}/SUMIF({r.active_range},"YES",{direct_range}),'
            f"{col(r.ahp_w_col)}{row}))",
        )
        for c in (r.geo_col, r.ahp_w_col, r.weight_col):
            _style(ws.cell(row, c), bg=TEAL_PALE, fmt="0.0000", bold=c == r.weight_col)

    ws.cell(r.mask_row - 1, 2, "Helper: matrix with inactive FoMs set to 1")
    ws.cell(r.wrow, 2, "Helper: AHP weights (inactive = 0)")
    ws.cell(r.aw_row, 2, "A.w")
    ws.cell(r.lam_row, 2, "lambda = (A.w) / w")
    for i in range(n):
        for j in range(n):
            ws.cell(
                r.mask_row + i,
                FIRST + j,
                f'=IF(AND({r.active(i)}="YES",{r.active(j)}="YES"),'
                f"{col(FIRST + j)}{FOM_ROW + i},1)",
            )
        ws.cell(r.wrow, FIRST + i, f'=IF({r.active(i)}="YES",{col(r.ahp_w_col)}{FOM_ROW + i},0)')
        mask = f"{col(FIRST)}{r.mask_row + i}:{col(FIRST + n - 1)}{r.mask_row + i}"
        wrow = f"${col(FIRST)}${r.wrow}:${col(FIRST + n - 1)}${r.wrow}"
        ws.cell(r.aw_row, FIRST + i, f'=IF({r.active(i)}="YES",SUMPRODUCT({mask},{wrow}),"")')
        ws.cell(
            r.lam_row,
            FIRST + i,
            f'=IF({r.active(i)}="YES",{col(FIRST + i)}{r.aw_row}/{col(FIRST + i)}{r.wrow},"")',
        )

    for c, label in enumerate(
        ["n (active)", "lambda max", "RI", "CI", "CR", "CR <= 10%?"], start=2
    ):
        _header(ws, r.res_row - 1, c, label)
    lam = f"{col(FIRST)}{r.lam_row}:{col(FIRST + n - 1)}{r.lam_row}"
    ri_range = f"$C${r.ri_row}:${col(FIRST + len(SAATY_RI) - 1)}${r.ri_row}"
    ws.cell(r.res_row, 2, f"={r.n_active}")
    ws.cell(r.res_row, 3, f"=AVERAGE({lam})")
    ws.cell(r.res_row, 4, f"=INDEX({ri_range},B{r.res_row})")
    ws.cell(r.res_row, 5, f"=IF(B{r.res_row}>2,(C{r.res_row}-B{r.res_row})/(B{r.res_row}-1),0)")
    ws.cell(r.res_row, 6, f"=IF(D{r.res_row}>0,E{r.res_row}/D{r.res_row},0)")
    ws.cell(r.res_row, 7, f'=IF(F{r.res_row}<={CR_THRESHOLD},"YES","NO - revise judgments")')
    for c in range(2, 8):
        _style(ws.cell(r.res_row, c), bg=TEAL_PALE, bold=True, fmt="0.0000")
    ws.cell(r.res_row, 6).number_format = "0.0%"
    ws.cell(r.ri_row, 2, "Saaty RI(n), n = 1..9")
    for k, n_value in enumerate(sorted(SAATY_RI)):
        ws.cell(r.ri_row, FIRST + k, SAATY_RI[n_value])


def _scoring_sheet(ws: Worksheet, result: TradeoffResult, r: _Refs) -> None:
    m = r.m
    _title(
        ws,
        "SCORING - raw values (yellow) and normalized shares",
        "Normalized: v/sum (higher) or (sum-v)/((n-1) sum) (lower); each row sums to 1",
    )
    ws.column_dimensions["B"].width = 30
    _header(ws, 6, 2, "Figure of merit")
    _header(ws, 6, r.sum_col, "Row sum")
    for s, label in enumerate(result.labels):
        _header(ws, 6, FIRST + s, label)
        _header(ws, 6, r.norm_col + s, f"{label} (norm.)")
        ws.column_dimensions[col(FIRST + s)].width = 15
        ws.column_dimensions[col(r.norm_col + s)].width = 15
    for k, f in enumerate(result.foms):
        row = FOM_ROW + k
        ws.cell(row, 2, f"={r.name(k)}")
        for s in range(m):
            value = result.table[s][f.id].value
            _style(ws.cell(row, FIRST + s, value), inp=True, fmt="0.000")
        values = f"{col(FIRST)}{row}:{col(FIRST + m - 1)}{row}"
        ws.cell(row, r.sum_col, f"=SUM({values})")
        total = f"${col(r.sum_col)}{row}"
        for s in range(m):
            v = f"{col(FIRST + s)}{row}"
            ws.cell(
                row,
                r.norm_col + s,
                f'=IF({total}=0,1/{m},IF({r.direction(k)}="higher",{v}/{total},'
                f"({total}-{v})/(({m}-1)*{total})))",
            )
            _style(ws.cell(row, r.norm_col + s), bg=TEAL_PALE, fmt="0.0000")


def _decision_sheet(ws: Worksheet, result: TradeoffResult, r: _Refs) -> None:
    n, m = r.n, r.m
    _title(
        ws,
        "DECISION - weighted normalized values, score and rank",
        "Cell = normalized share x weight; score = column sum; rank 1 = best",
    )
    ws.column_dimensions["B"].width = 30
    _header(ws, DEC_ROW - 1, 2, "Figure of merit")
    _header(ws, DEC_ROW - 1, FIRST, "Weight")
    for s in range(m):
        ws.cell(DEC_ROW - 1, FIRST + 1 + s, f"='3. Scoring'!{col(FIRST + s)}6")
        _style(ws.cell(DEC_ROW - 1, FIRST + 1 + s), bold=True, fg=WHITE, bg=TEAL_MID)
        ws.column_dimensions[col(FIRST + 1 + s)].width = 15
    for k in range(n):
        row = DEC_ROW + k
        ws.cell(row, 2, f"={r.name(k)}")
        _style(ws.cell(row, FIRST, f"={r.weight(k)}"), fmt="0.0000")
        for s in range(m):
            _style(ws.cell(row, FIRST + 1 + s, f"={r.norm(k, s)}*{r.weight(k)}"), fmt="0.0000")
    ws.cell(r.final_row, 2, "FINAL SCORE")
    ws.cell(r.rank_row, 2, "RANK (1 = best)")
    for s in range(m):
        c = col(FIRST + 1 + s)
        ws.cell(r.final_row, FIRST + 1 + s, f"=SUM({c}{DEC_ROW}:{c}{DEC_ROW + n - 1})")
        ws.cell(r.rank_row, FIRST + 1 + s, f"=RANK({c}{r.final_row},{r.scores_range},0)")
        _style(ws.cell(r.final_row, FIRST + 1 + s), bold=True, fg=WHITE, bg=TEAL_DARK, fmt="0.0000")
        _style(ws.cell(r.rank_row, FIRST + 1 + s), bold=True, bg=TEAL_PALE)
    chart = BarChart()
    chart.title = "Final weighted score"
    chart.add_data(
        Reference(
            ws, min_col=FIRST + 1, max_col=FIRST + m, min_row=r.final_row, max_row=r.final_row
        ),
        from_rows=True,
    )
    chart.set_categories(
        Reference(
            ws, min_col=FIRST + 1, max_col=FIRST + m, min_row=DEC_ROW - 1, max_row=DEC_ROW - 1
        )
    )
    chart.legend = None
    ws.add_chart(chart, f"B{r.rank_row + 2}")


def _sensitivity_sheet(ws: Worksheet, r: _Refs) -> None:
    n, m = r.n, r.m
    pairs = [(i, j) for i in range(m) for j in range(i + 1, m)]
    dk_col, sens_col = FIRST + 1 + len(pairs), FIRST + 2 + len(pairs)
    _title(
        ws,
        "SENSITIVITY - criticality D_k and 1/D_k",
        "delta' = 100|S_j-S_i| / |n_jk-n_ik| / w_k; only feasible values (0, 100%] are shown",
    )
    ws.column_dimensions["B"].width = 30
    _header(ws, DEC_ROW - 1, 2, "Figure of merit")
    _header(ws, DEC_ROW - 1, FIRST, "Weight")
    for p, (i, j) in enumerate(pairs):
        ws.cell(
            DEC_ROW - 1,
            FIRST + 1 + p,
            f"='3. Scoring'!{col(FIRST + i)}6&\" vs \"&'3. Scoring'!{col(FIRST + j)}6",
        )
        _style(ws.cell(DEC_ROW - 1, FIRST + 1 + p), bold=True, fg=WHITE, bg=TEAL_MID, wrap=True)
        ws.column_dimensions[col(FIRST + 1 + p)].width = 14
    _header(ws, DEC_ROW - 1, dk_col, "D_k (%)")
    _header(ws, DEC_ROW - 1, sens_col, "1 / D_k")
    for k in range(n):
        row = DEC_ROW + k
        ws.cell(row, 2, f"={r.name(k)}")
        _style(ws.cell(row, FIRST, f"={r.weight(k)}"), fmt="0.0000")
        for p, (i, j) in enumerate(pairs):
            expr = (
                f"100*ABS({r.score(j)}-{r.score(i)})/ABS({r.norm(k, j)}-{r.norm(k, i)})"
                f"/{r.weight(k)}"
            )
            ws.cell(row, FIRST + 1 + p, f'=IFERROR(IF(AND({expr}>0,{expr}<=100),{expr},""),"")')
            _style(ws.cell(row, FIRST + 1 + p), fmt="0.0")
        pair_range = f"{col(FIRST + 1)}{row}:{col(FIRST + len(pairs))}{row}"
        ws.cell(row, dk_col, f'=IF(COUNT({pair_range})=0,"",MIN({pair_range}))')
        ws.cell(row, sens_col, f'=IF({col(dk_col)}{row}="","",1/{col(dk_col)}{row})')
        _style(ws.cell(row, dk_col), bold=True, bg=TEAL_PALE, fmt="0.0")
        _style(ws.cell(row, sens_col), bold=True, bg=TEAL_PALE, fmt="0.0000")


def _recommendation_sheet(ws: Worksheet, result: TradeoffResult, r: _Refs) -> None:
    n = r.n
    dk_col = col(FIRST + 1 + r.m * (r.m - 1) // 2)
    dk_range = f"'5. Sensitivity'!${dk_col}${DEC_ROW}:${dk_col}${DEC_ROW + n - 1}"
    names = f"'5. Sensitivity'!$B${DEC_ROW}:$B${DEC_ROW + n - 1}"
    _title(ws, "RECOMMENDATION")
    ws.column_dimensions["B"].width = 34
    ws.column_dimensions["C"].width = 90
    rows = [
        (
            "Winner (highest score)",
            f"=INDEX({r.labels_range},MATCH(MAX({r.scores_range}),{r.scores_range},0))",
        ),
        ("Winner score", f"=MAX({r.scores_range})"),
        (
            "Runner-up",
            f"=INDEX({r.labels_range},MATCH(LARGE({r.scores_range},2),{r.scores_range},0))",
        ),
        ("Margin (winner - runner-up)", f"=MAX({r.scores_range})-LARGE({r.scores_range},2)"),
        ("Consistency ratio (AHP mode)", f"={r.cr}"),
        (
            "Most critical FoM (smallest D_k)",
            f'=IFERROR(INDEX({names},MATCH(MIN({dk_range}),{dk_range},0)),"none: ranking robust")',
        ),
        ("AI comment (from the app)", result.ai_comment or "(none)"),
        ("Method", result.method),
    ]
    for k, (label, value) in enumerate(rows):
        _style(ws.cell(5 + k, 2, label), bold=True, bg=GREY, fg=NAVY)
        _style(ws.cell(5 + k, 3, value), wrap=True)
        ws.row_dimensions[5 + k].height = 30 if k < 6 else 60


def _sources_sheet(ws: Worksheet, result: TradeoffResult, evaluations: list[Evaluation]) -> None:
    _title(ws, "DATA & SOURCES", "Inputs behind every computed FoM value")
    heads = [
        "Scenario",
        "Site id",
        "Lat (deg)",
        "Lon E (deg)",
        "Window start (UTC)",
        "Window end (UTC)",
        "Step (min)",
        "Landing precision (m)",
        "Operating range (m)",
        "Traverse limit (deg)",
        "Observer height (m)",
        "Horizon DEM",
        "Terrain DEM",
    ]
    for c, text in enumerate(heads, start=2):
        _header(ws, 5, c, text)
        ws.column_dimensions[col(c)].width = 18
    for s, (label, e) in enumerate(zip(result.labels, evaluations, strict=True)):
        a = e.area
        row = [
            label,
            e.site_id or "(custom point)",
            e.location.lat_deg,
            e.location.lon_deg,
            e.window.start_utc.isoformat(),
            e.window.end_utc.isoformat(),
            e.window.step_minutes,
            a.landing_precision_m,
            a.operating_range_m,
            a.traverse_slope_limit_deg,
            a.observer_height_above_ground_m,
            e.horizon.dem_source,
            e.terrain.dem_source,
        ]
        for c, value in enumerate(row, start=2):
            ws.cell(6 + s, c, value)
    base = 8 + len(evaluations)
    notes = [
        "Ephemerides: JPL Horizons API, https://ssd-api.jpl.nasa.gov/doc/horizons.html (NASA JPL).",
        "Topography: NASA LRO LOLA gridded DEMs, data set LRO-L-LOLA-4-GDR-V1.0, PDS Geosciences.",
        "User-supplied FoMs (sheet 1, User-supplied = YES) are estimates entered by the user.",
    ]
    for k, text in enumerate(notes):
        ws.cell(base + k, 2, text)
