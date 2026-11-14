# ABOUTME: Reachable share of the operations disk (decision D32): least-cost paths over slope cells
# ABOUTME: Cells steeper than the traverse limit are walls; paths may detour around them

"""Share of the operations disk reachable on foot or by rover from the landing point.

Each grid cell is traversable when its slope is at most the traverse limit (decision D32;
20 deg for EVAs, 15 deg for a VIPER-class rover). From the center cell we compute the length of
the shortest path to every cell, moving between the 8 neighbours through traversable cells only
(Dijkstra on the grid, ``skimage.graph.MCP_Geometric``). A cell counts as reachable when that
path is no longer than the operating range; the share is reachable cells over all cells of the
disk of radius ``operating_range_m``.

Grid bias: 8-direction moves make open-ground paths up to ~8 % longer than the straight line
(e.g. toward 22.5 deg), which alone would mark the edge of a flat disk unreachable. So the
length compared with the range is the straight-line distance plus the detour caused by
obstacles (found path minus the open-grid path), which is exact on open ground.

Corner squeeze: a diagonal move between two steep cells that touch only at a corner would cross
a gap of zero width (a one-pixel diagonal wall would leak). Such pinches are closed by marking one
of the two open cells of the 2 x 2 block impassable, a slightly conservative choice.

Limits, by design: only slope is considered (no boulders, no lighting), slopes are on the DEM
pixel baseline, and uphill and cross-slope count the same.
"""

from __future__ import annotations

import numpy as np
from skimage.graph import MCP_Geometric

from lunarnav.terrain.slope import SlopeGrid

IMPASSABLE = -1.0  # MCP_Geometric never enters cells with a negative cost


def path_lengths_m(grid: SlopeGrid, traverse_slope_limit_deg: float) -> np.ndarray:
    """Shortest traversable path length from the center to every cell, meters.

    Args:
        grid: Slope grid centered on the starting point.
        traverse_slope_limit_deg: Steepest slope a path may cross, degrees.

    Returns:
        Path lengths, meters, same shape as the grid; ``inf`` where no path exists. The start
        cell is always 0, even if it is itself steep (the vehicle is already there).
    """
    blocked = _close_corner_squeezes(grid.slope_deg > traverse_slope_limit_deg)
    start = (grid.center, grid.center)
    blocked[start] = False
    costs = np.where(blocked, IMPASSABLE, 1.0)
    cumulative, _ = MCP_Geometric(costs, fully_connected=True).find_costs([start])
    lengths = np.asarray(cumulative, dtype=float) * grid.step_m
    lengths[costs < 0] = np.inf
    lengths[~np.isfinite(lengths)] = np.inf
    return lengths


def reachable_fraction(
    grid: SlopeGrid, operating_range_m: float, traverse_slope_limit_deg: float
) -> float | None:
    """Share of the disk of radius ``operating_range_m`` reachable within that path length.

    Args:
        grid: Slope grid centered on the landing point, covering the disk.
        operating_range_m: Disk radius and longest allowed path, meters.
        traverse_slope_limit_deg: Steepest slope a path may cross, degrees.

    Returns:
        The share in [0, 1], or None when ``operating_range_m`` is 0 (no operations area).
    """
    if operating_range_m <= 0.0:
        return None
    inside = grid.inside(operating_range_m)
    lengths = path_lengths_m(grid, traverse_slope_limit_deg)
    straight = np.hypot(grid.east_m, grid.north_m)
    detour = lengths - _open_grid_lengths_m(grid)  # 0 on open ground, inf where unreachable
    reachable = inside & (straight + detour <= operating_range_m + 1e-6)
    return float(reachable.sum() / inside.sum())


def _open_grid_lengths_m(grid: SlopeGrid) -> np.ndarray:
    """Shortest 8-connected path from the center on an obstacle-free grid (octile distance)."""
    dr = np.abs(np.rint(grid.north_m / grid.step_m))
    dc = np.abs(np.rint(grid.east_m / grid.step_m))
    lo, hi = np.minimum(dr, dc), np.maximum(dr, dc)
    return (hi - lo + np.sqrt(2.0) * lo) * grid.step_m


def _close_corner_squeezes(blocked: np.ndarray) -> np.ndarray:
    """Block one open cell of every 2 x 2 window whose blocked cells touch only diagonally."""
    out = blocked.copy()
    a, b = blocked[:-1, :-1], blocked[:-1, 1:]  # top-left, top-right
    c, d = blocked[1:, :-1], blocked[1:, 1:]  # bottom-left, bottom-right
    main = a & d & ~b & ~c  # blocked on the main diagonal: close the top-right cell
    anti = b & c & ~a & ~d  # blocked on the anti-diagonal: close the top-left cell
    out[:-1, 1:] |= main
    out[:-1, :-1] |= anti
    return out
