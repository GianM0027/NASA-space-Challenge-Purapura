# ABOUTME: Known-answer tests of the reachable share (decision D32): paths, walls, gaps, rings
# ABOUTME: Synthetic slope grids built directly, so expected values come from counting cells

import numpy as np
import pytest

from lunarnav.terrain.reachability import path_lengths_m, reachable_fraction
from lunarnav.terrain.slope import SlopeGrid

STEP = 20.0
K = 15  # grid of 31 x 31 cells, center at (15, 15)
SQRT2 = np.sqrt(2.0)


def grid(slope: np.ndarray) -> SlopeGrid:
    axis = np.arange(-K, K + 1) * STEP
    east, north = np.meshgrid(axis, axis)
    return SlopeGrid(east, north, np.zeros_like(east), slope, STEP, K)


def flat() -> np.ndarray:
    return np.zeros((2 * K + 1, 2 * K + 1))


def octile(a: tuple[int, int], b: tuple[int, int]) -> float:
    """Shortest 8-connected path length between two cells on an open grid, meters."""
    dr, dc = abs(a[0] - b[0]), abs(a[1] - b[1])
    return (max(dr, dc) - min(dr, dc) + SQRT2 * min(dr, dc)) * STEP


def test_open_ground_paths_are_straight_and_diagonal_moves() -> None:
    lengths = path_lengths_m(grid(flat()), 20.0)
    assert lengths[K, K] == 0.0
    assert lengths[K, K + 7] == pytest.approx(7 * STEP)
    assert lengths[K + 4, K + 4] == pytest.approx(4 * SQRT2 * STEP)
    assert lengths[K + 2, K + 6] == pytest.approx(octile((K, K), (K + 2, K + 6)))


def test_flat_disk_is_fully_reachable() -> None:
    assert reachable_fraction(grid(flat()), 200.0, 20.0) == 1.0


def test_no_operations_area_gives_none() -> None:
    assert reachable_fraction(grid(flat()), 0.0, 20.0) is None


def test_slope_equal_to_the_limit_is_traversable() -> None:
    assert reachable_fraction(grid(np.full((2 * K + 1, 2 * K + 1), 20.0)), 200.0, 20.0) == 1.0
    assert reachable_fraction(grid(np.full((2 * K + 1, 2 * K + 1), 20.1)), 200.0, 20.0) < 0.01


def test_wall_without_gap_cuts_off_the_far_side() -> None:
    slope = flat()
    slope[:, K + 3] = 30.0  # wall three cells east of the center, from edge to edge
    g = grid(slope)
    inside = g.inside(200.0)
    expected = (inside & (g.east_m < 3 * STEP)).sum() / inside.sum()  # wall cells count as lost
    assert reachable_fraction(g, 200.0, 20.0) == pytest.approx(expected)
    assert np.isinf(path_lengths_m(g, 20.0)[K, K + 5])


def test_gap_in_the_wall_allows_a_detour_of_known_length() -> None:
    slope = flat()
    slope[: K + 4, K + 3] = 30.0  # wall ends 4 rows north of the center row; gap beyond it
    lengths = path_lengths_m(grid(slope), 20.0)
    gap = (K + 4, K + 3)  # first open cell of the wall column
    target = (K, K + 5)  # just behind the wall, on the center row
    assert lengths[target] == pytest.approx(octile((K, K), gap) + octile(gap, target))


def test_detour_longer_than_the_range_does_not_count() -> None:
    slope = flat()
    slope[: K + 10, K + 3] = 30.0  # gap 10 rows away: the detour exceeds a 150 m range
    g = grid(slope)
    short_range = reachable_fraction(g, 150.0, 20.0)
    inside = g.inside(150.0)
    near_side = (inside & (g.east_m < 3 * STEP)).sum() / inside.sum()
    assert short_range == pytest.approx(near_side)
    assert reachable_fraction(g, 300.0, 20.0) > (g.inside(300.0) & (g.east_m < 60)).mean()


def test_ring_wall_keeps_only_the_inside() -> None:
    g0 = grid(flat())
    radius = np.hypot(g0.east_m, g0.north_m)
    slope = np.where(np.abs(radius - 5 * STEP) <= STEP / 2, 30.0, 0.0)  # closed ring at 100 m
    g = grid(slope)
    inside = g.inside(250.0)
    interior = (inside & (radius < 5 * STEP - STEP / 2)).sum() / inside.sum()
    # Nothing outside the ring is reachable; closing corner squeezes may cost a few inner cells.
    share = reachable_fraction(g, 250.0, 20.0)
    assert interior * 0.85 <= share <= interior


def test_one_pixel_diagonal_wall_does_not_leak() -> None:
    slope = flat()
    for i in range(2 * K + 1 - 3):
        slope[i, i + 3] = 30.0  # diagonal wall 3 cells east of the center, cells touch at corners
    lengths = path_lengths_m(grid(slope), 20.0)
    assert np.isfinite(lengths[K + 5, K - 5])  # same side as the start
    assert np.isinf(lengths[K - 5, K + 5])  # across the wall: no squeezing between corners


def test_steep_start_cell_does_not_trap_the_vehicle() -> None:
    slope = flat()
    slope[K, K] = 45.0
    assert reachable_fraction(grid(slope), 200.0, 20.0) == 1.0
