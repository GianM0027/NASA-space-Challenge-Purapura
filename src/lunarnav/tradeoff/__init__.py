# ABOUTME: tradeoff module: AHP trade-off between compared scenarios (UI-3, TO-1 to TO-4, TO-6)
# ABOUTME: Owner: Federico (decision D37); public API uses lunarnav.contracts types only

"""AHP trade-off between compared scenarios (spec section 4.8)."""

from lunarnav.contracts import TradeoffAnalyzer
from lunarnav.tradeoff.analyzer import LunarTradeoff


def build_tradeoff() -> TradeoffAnalyzer:
    """Build the trade-off analyzer the API wires in (spec IF-5, decision D39).

    Returns:
        A LunarTradeoff (no upstream dependencies).
    """
    return LunarTradeoff()


__all__ = ["LunarTradeoff", "build_tradeoff"]
