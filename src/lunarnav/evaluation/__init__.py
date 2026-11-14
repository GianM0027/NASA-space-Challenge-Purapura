# ABOUTME: evaluation module: ephemerides plus horizon masks into visibility series and metrics
# ABOUTME: Owner: Federico (MISSION.md section 4); public API uses lunarnav.contracts types only

"""Combines ephemerides and horizon masks into visibility series and metrics."""

from lunarnav.contracts import EphemerisProvider, Evaluator, TerrainProvider
from lunarnav.evaluation.evaluator import LunarEvaluator


def build_evaluator(ephemeris: EphemerisProvider, terrain: TerrainProvider) -> Evaluator:
    """Build the evaluator the API wires in (spec IF-5, decision D21).

    Args:
        ephemeris: The ephemeris provider chosen by the API (real or placeholder).
        terrain: The terrain provider chosen by the API (real or placeholder).

    Returns:
        A LunarEvaluator over the given providers.
    """
    return LunarEvaluator(ephemeris, terrain)


__all__ = ["LunarEvaluator", "build_evaluator"]
