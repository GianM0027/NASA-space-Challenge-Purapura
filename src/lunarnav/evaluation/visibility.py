# ABOUTME: Visibility against a horizon mask and run/event metrics on sampled series (EVA-1)
# ABOUTME: Decision D20 definitions: body center above the mask, runs n x step, first-sample events

"""Visibility of a body against the terrain horizon, and metrics on the sampled result.

Definitions (spec section 3, decision D20):

* A body is visible when its center elevation is strictly above the horizon mask interpolated
  at its azimuth (linear interpolation, periodic over 360 degrees).
* A run of n consecutive samples in one state lasts n * step.
* A longest run is truncated when at least one run of that length starts at the first sample or
  ends at the last one: the window may cut it, so its duration is a lower bound (decision D29).
* An event (sunset, sunrise, ...) is the time of the first sample in the new state after the
  window start; None when no such transition happens inside the window.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np


def horizon_at(
    mask_azimuth_deg: np.ndarray, mask_elevation_deg: np.ndarray, azimuth_deg: np.ndarray
) -> np.ndarray:
    """Horizon elevation at arbitrary azimuths, by periodic linear interpolation of the mask.

    Args:
        mask_azimuth_deg: Strictly increasing mask azimuths in [0, 360), degrees.
        mask_elevation_deg: Horizon elevation at each mask azimuth, degrees.
        azimuth_deg: Azimuths to evaluate, degrees (any values; wrapped modulo 360).

    Returns:
        Horizon elevation at each azimuth, degrees.
    """
    return np.interp(np.mod(azimuth_deg, 360.0), mask_azimuth_deg, mask_elevation_deg, period=360.0)


def is_visible(elevation_deg: np.ndarray, horizon_deg: np.ndarray) -> np.ndarray:
    """True where the body center is strictly above the horizon."""
    return np.asarray(elevation_deg) > np.asarray(horizon_deg)


def longest_run(flags: np.ndarray, state: bool, step_h: float) -> tuple[float, bool]:
    """Longest run of consecutive samples equal to ``state``, and whether the window may cut it.

    Args:
        flags: Per-sample booleans.
        state: The state whose runs are measured.
        step_h: Sampling step, hours.

    Returns:
        (n * step_h for the longest run of n samples, truncated). ``truncated`` is True when at
        least one run of the maximal length starts at the first sample or ends at the last one.
        A state that never occurs gives (0.0, False).
    """
    f = np.asarray(flags) == state
    hits = np.concatenate(([0], f.astype(np.int8), [0]))
    edges = np.flatnonzero(np.diff(hits))  # alternating run starts and ends (exclusive)
    if edges.size == 0:
        return 0.0, False
    starts, ends = edges[::2], edges[1::2]
    lengths = ends - starts
    best = lengths.max()
    longest = lengths == best
    truncated = bool(np.any(longest & ((starts == 0) | (ends == f.size))))
    return float(best * step_h), truncated


def first_transition(times: list[datetime], flags: np.ndarray, to: bool) -> datetime | None:
    """Time of the first sample that enters state ``to`` from the other state.

    Args:
        times: Sample times, aligned with ``flags``.
        flags: Per-sample booleans.
        to: The state entered (False for a set, True for a rise).

    Returns:
        The time, or None when the transition does not happen.
    """
    f = np.asarray(flags, dtype=bool)
    entered = np.flatnonzero((f[1:] == to) & (f[:-1] != to))
    return times[int(entered[0]) + 1] if entered.size else None
