# ABOUTME: LunarTradeoff: the TradeoffAnalyzer port (D39); contract models in, engine, contract out
# ABOUTME: Converts TradeoffSettings to FoM columns and judgments, and the outcome to TradeoffResult

"""TradeoffAnalyzer implementation over the module's engine (spec 4.8, decision D39)."""

from __future__ import annotations

from lunarnav.contracts import (
    Evaluation,
    FigureOfMerit,
    FomDirection,
    FomScore,
    FomSensitivity,
    PairwiseJudgment,
    TradeoffResult,
    TradeoffSettings,
)
from lunarnav.tradeoff.ahp import Judgment
from lunarnav.tradeoff.engine import METHOD, TradeoffOutcome, run_tradeoff
from lunarnav.tradeoff.export import export_xlsx
from lunarnav.tradeoff.foms import FomSpec, UserFomInput, computed_columns, user_columns
from lunarnav.tradeoff.scoring import Direction


class LunarTradeoff:
    """AHP trade-off over 2 to 4 evaluated scenarios."""

    def analyze(self, evaluations: list[Evaluation], settings: TradeoffSettings) -> TradeoffResult:
        """Score the scenarios on every figure of merit with the settings' weights.

        Args:
            evaluations: One evaluation per scenario, in the order of ``settings.labels``.
            settings: Labels, weights or pairwise judgments, user FoMs, excluded FoMs.

        Returns:
            The trade-off table, weights, scores, ranking and sensitivity (``ai_comment`` None).

        Raises:
            ValueError: If the evaluations do not match the labels, a judgment or weight names an
                unknown FoM, or more than 9 FoMs remain.
        """
        if len(evaluations) != len(settings.labels):
            raise ValueError(f"{len(evaluations)} evaluations for {len(settings.labels)} labels")
        excluded = list(settings.excluded_foms)
        user = [
            UserFomInput(u.name, u.unit, Direction(u.direction.value), u.values)
            for u in settings.user_foms
        ]
        columns = computed_columns(evaluations, excluded) + user_columns(
            user, len(evaluations), excluded
        )
        judgments = (
            [Judgment(j.a, j.b, j.value, j.source) for j in settings.judgments]
            if settings.judgments
            else None
        )
        outcome = run_tradeoff(columns, judgments=judgments, direct_weights=settings.weights)
        return to_result(outcome, settings.labels)

    def export_xlsx(self, result: TradeoffResult, evaluations: list[Evaluation]) -> bytes:
        """Write the trade-off as a live Excel workbook (spec TO-4).

        Args:
            result: The trade-off to export, AI comment included.
            evaluations: The evaluations behind it, for the data and sources sheet.

        Returns:
            The .xlsx file content.
        """
        return export_xlsx(result, evaluations)


def to_result(outcome: TradeoffOutcome, labels: list[str]) -> TradeoffResult:
    """Convert the engine outcome to the contract model."""
    ids = [f.id for f in outcome.foms]
    table = [
        {
            fid: FomScore(
                value=float(outcome.values[s, k]), normalized=float(outcome.normalized[s, k])
            )
            for k, fid in enumerate(ids)
        }
        for s in range(len(labels))
    ]
    return TradeoffResult(
        labels=list(labels),
        foms=[_fom(f) for f in outcome.foms],
        weights={fid: float(w) for fid, w in zip(ids, outcome.weights, strict=True)},
        weight_method=outcome.weight_method,
        judgments=[
            PairwiseJudgment(a=j.a, b=j.b, value=j.value, source=j.source)
            for j in outcome.judgments
        ],
        consistency_ratio=outcome.consistency_ratio,
        table=table,
        scores=[float(s) for s in outcome.scores],
        ranking=list(outcome.ranking),
        method=METHOD,
        sensitivity=[
            FomSensitivity(
                fom_id=s.fom_id,
                min_change_percent=s.min_change_percent,
                sensitivity=s.sensitivity,
            )
            for s in outcome.sensitivity
        ],
    )


def _fom(spec: FomSpec) -> FigureOfMerit:
    return FigureOfMerit(
        id=spec.id,
        name=spec.name,
        unit=spec.unit,
        direction=FomDirection(spec.direction.value),
        user_supplied=spec.user_supplied,
        source=spec.source,
    )
