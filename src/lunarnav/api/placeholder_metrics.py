# ABOUTME: Reference implementation of the visibility metrics (spec section 3) for the placeholder
# ABOUTME: Owner: Gian. Used until the real evaluator lands; its tests pin down the definitions

"""Visibility metrics and horizon interpolation, written for clarity rather than speed.

This is the placeholder evaluator's engine and the generator of ``data/examples``. The real
evaluator (Federico, spec EVA-1) may compute the same quantities its own way, but must agree with
the definitions in spec section 3, which the tests of this module pin down with known answers.
"""

from __future__ import annotations

from bisect import bisect_right
from datetime import datetime

from lunarnav.contracts import VisibilityMetrics


def longest_run(flags: list[bool], state: bool, step_h: float) -> tuple[float, bool]:
    """Return the longest run of ``state`` and whether it may be cut by the window.

    Args:
        flags: Per-sample states.
        state: The state whose runs are measured.
        step_h: Sampling step, hours; a run of n samples lasts n * step_h.

    Returns:
        (duration in hours, truncated). ``truncated`` is True when at least one run of the
        maximal length starts at the first sample or ends at the last one, so the true duration
        may be longer than the window shows. A state that never occurs gives (0.0, False).
    """
    best = 0
    truncated = False
    start = 0
    for i in range(len(flags) + 1):
        if i < len(flags) and flags[i] is state:
            continue
        length = i - start
        if length > 0:
            at_edge = start == 0 or i == len(flags)
            if length > best:
                best, truncated = length, at_edge
            elif length == best:
                truncated = truncated or at_edge
        start = i + 1
    return best * step_h, truncated


def first_transition(times: list[datetime], flags: list[bool], to: bool) -> datetime | None:
    """Return the time of the first sample entering state ``to`` after the start, or None."""
    for i in range(1, len(flags)):
        if flags[i] is to and flags[i - 1] is not to:
            return times[i]
    return None


def horizon_at(azimuth_deg: list[float], elevation_deg: list[float], azimuth: float) -> float:
    """Interpolate a horizon mask linearly at ``azimuth``, wrapping around 360 degrees.

    Args:
        azimuth_deg: Strictly increasing mask azimuths in [0, 360), degrees.
        elevation_deg: Horizon elevation at each mask azimuth, degrees.
        azimuth: Query azimuth, degrees, any value (reduced modulo 360).

    Returns:
        Horizon elevation at ``azimuth``, degrees.
    """
    a = azimuth % 360.0
    i = bisect_right(azimuth_deg, a) - 1  # last grid azimuth <= a; -1 means before the first
    lo_az, lo_el = (
        (azimuth_deg[i], elevation_deg[i])
        if i >= 0
        else (
            azimuth_deg[-1] - 360.0,
            elevation_deg[-1],
        )
    )
    j = i + 1
    hi_az, hi_el = (
        (azimuth_deg[j], elevation_deg[j])
        if j < len(azimuth_deg)
        else (
            azimuth_deg[0] + 360.0,
            elevation_deg[0],
        )
    )
    if hi_az == lo_az:
        return lo_el
    return lo_el + (hi_el - lo_el) * (a - lo_az) / (hi_az - lo_az)


def _mean(values: list[float]) -> float | None:
    """Return the mean of ``values``, or None when empty."""
    return sum(values) / len(values) if values else None


def compute_metrics(
    times: list[datetime],
    sun_elevation_deg: list[float],
    sun_visible: list[bool],
    earth_elevation_deg: list[float],
    earth_visible: list[bool],
    step_h: float,
) -> VisibilityMetrics:
    """Compute the summary metrics of one evaluation from its aligned per-sample series.

    Args:
        times: Sample times.
        sun_elevation_deg: Geometric Sun elevation per sample, degrees.
        sun_visible: Sun center above the terrain horizon per sample.
        earth_elevation_deg: Geometric Earth elevation per sample, degrees.
        earth_visible: Earth center above the terrain horizon per sample.
        step_h: Sampling step, hours.

    Returns:
        The metrics, following spec section 3.
    """
    n = len(times)
    light_h, light_cut = longest_run(sun_visible, True, step_h)
    dark_h, dark_cut = longest_run(sun_visible, False, step_h)
    contact_h, contact_cut = longest_run(earth_visible, True, step_h)
    outage_h, outage_cut = longest_run(earth_visible, False, step_h)
    both = [s and e for s, e in zip(sun_visible, earth_visible, strict=True)]
    return VisibilityMetrics(
        illumination_fraction=sum(sun_visible) / n,
        sun_elevation_max_deg=max(sun_elevation_deg),
        sun_elevation_mean_visible_deg=_mean(
            [e for e, v in zip(sun_elevation_deg, sun_visible, strict=True) if v]
        ),
        longest_light_h=light_h,
        longest_light_truncated=light_cut,
        longest_dark_h=dark_h,
        longest_dark_truncated=dark_cut,
        earth_visibility_fraction=sum(earth_visible) / n,
        earth_elevation_mean_visible_deg=_mean(
            [e for e, v in zip(earth_elevation_deg, earth_visible, strict=True) if v]
        ),
        longest_earth_visible_h=contact_h,
        longest_earth_visible_truncated=contact_cut,
        longest_earth_hidden_h=outage_h,
        longest_earth_hidden_truncated=outage_cut,
        sun_and_earth_visible_fraction=sum(both) / n,
        sun_visible_at_start=sun_visible[0],
        earth_visible_at_start=earth_visible[0],
        next_sunset_utc=first_transition(times, sun_visible, False),
        next_sunrise_utc=first_transition(times, sun_visible, True),
        next_earthset_utc=first_transition(times, earth_visible, False),
        next_earthrise_utc=first_transition(times, earth_visible, True),
    )
