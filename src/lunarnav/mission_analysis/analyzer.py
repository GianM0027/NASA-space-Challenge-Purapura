# ABOUTME: RobustnessAnalyzer (MA-1, MA-2, MA-3): date-slip sweep, dispersion samples, plain summary
# ABOUTME: Implements the MissionAnalyzer port on top of any Evaluator (owner: Michael, D37)

"""Mission analysis: how robust a site is to launch slips and to where exactly the lander lands.

* MA-1: the nominal window shifted by each offset: +1, +3, +7, +14 days (spec) plus one synodic
  month, which shows when the same lighting comes back (Michael's decision).
* MA-2: points on two rings inside the landing-precision disk (R/2 and R, every 45 deg), each
  evaluated as a landing point over the nominal window (Michael's decision: dispersion means
  landing dispersion; measured spreads below).
* MA-3: a plain-language summary that only quotes numbers present in the report; it adds the
  Earth link when the Earth is not visible all the time.

Measured with the real modules, 14-day window from 2026-11-20, landing precision 100 m (16 points):
sunlight 61-74 % at Malapert Massif (nominal 60 %; 8 points would show 64-73 %), 72-78 % at IM-2,
no change at Apollo 11; about 0.5 s warm and up to 17 s for a polar site not seen before.
"""

from __future__ import annotations

import math
from datetime import timedelta

from lunarnav.contracts import (
    DateShiftResult,
    DispersionSample,
    Evaluator,
    GeoPoint,
    MissionAnalyzer,
    OperationsArea,
    RobustnessReport,
    TimeWindow,
)

MOON_RADIUS_M = 1_737_400.0  # IAU mean radius, the LOLA reference sphere (contract convention)
# Synodic month (new Moon to new Moon) = one lunar day-night cycle at a site:
# 29.530589 days, NASA Moon Fact Sheet, https://nssdc.gsfc.nasa.gov/planetary/factsheet/moonfact.html
SYNODIC_MONTH_D = 29.530589
DEFAULT_SHIFTS_DAYS = (1.0, 3.0, 7.0, 14.0, SYNODIC_MONTH_D)  # spec MA-1 + one lunar cycle
DEFAULT_RINGS = 2  # sample rings at R/2 and R (MA-2)
DEFAULT_POINTS_PER_RING = 8  # every 45 deg: catches more of the spread at polar sites


class RobustnessAnalyzer:
    """Evaluates a site's sensitivity to date shifts and landing dispersion.

    Args:
        evaluator: Evaluator used for every case (nominal, shifted windows, sample points).
        rings: Number of sample rings, evenly spaced out to the landing-precision radius.
        points_per_ring: Samples per ring, evenly spaced in azimuth starting from north.
    """

    def __init__(
        self,
        evaluator: Evaluator,
        rings: int = DEFAULT_RINGS,
        points_per_ring: int = DEFAULT_POINTS_PER_RING,
    ) -> None:
        """Store the evaluator and the sampling pattern."""
        if rings < 0 or points_per_ring < 1:
            raise ValueError(f"invalid sampling: rings={rings}, points_per_ring={points_per_ring}")
        self.evaluator = evaluator
        self.rings = rings
        self.points_per_ring = points_per_ring

    def analyze(
        self,
        location: GeoPoint,
        window: TimeWindow,
        area: OperationsArea,
        shifts_days: list[float],
        site_id: str | None = None,
    ) -> RobustnessReport:
        """Evaluate the nominal case, each date shift and samples of the landing dispersion.

        Args:
            location: Nominal landing point.
            window: Nominal time window.
            area: Operations area; its landing-precision disk is sampled.
            shifts_days: Window shifts, days (positive = later); empty means the defaults. Each
                shift is rounded to a whole number of window steps so samples stay on the grid.
            site_id: Catalog id to echo in the report.

        Returns:
            The robustness report, with a summary quoting only its own numbers.
        """
        nominal = self.evaluator.evaluate(location, window, area, site_id).metrics
        date_shifts = []
        for requested in list(shifts_days) or list(DEFAULT_SHIFTS_DAYS):
            days = snap_shift_days(requested, window.step_minutes)
            metrics = self.evaluator.evaluate(location, shift_window(window, days), area).metrics
            date_shifts.append(DateShiftResult(shift_days=days, metrics=metrics))
        # Each sample asks "what if we land here": its slope is the landing-disk slope there.
        sample_area = area.model_copy(update={"operating_range_m": 0.0})
        dispersion = []
        for offset_m, point in sample_points(
            location, area.landing_precision_m, self.rings, self.points_per_ring
        ):
            evaluation = self.evaluator.evaluate(point, window, sample_area)
            dispersion.append(
                DispersionSample(
                    location=point,
                    offset_m=offset_m,
                    metrics=evaluation.metrics,
                    slope_max_deg=evaluation.terrain.landing_slope_max_deg,
                )
            )
        report = RobustnessReport(
            site_id=site_id, nominal=nominal, date_shifts=date_shifts, dispersion=dispersion
        )
        return report.model_copy(update={"summary": summarize(report)})


def build_mission_analyzer(evaluator: Evaluator) -> MissionAnalyzer:
    """Return the mission analyzer the API wires into the app (spec IF-5).

    Args:
        evaluator: The app's evaluator (real or placeholder).

    Returns:
        A ``RobustnessAnalyzer`` with the default sampling pattern.
    """
    return RobustnessAnalyzer(evaluator)


def snap_shift_days(days: float, step_minutes: int) -> float:
    """Round a shift to a whole number of window steps (keeps samples on the cache grid)."""
    steps = round(days * 1440 / step_minutes)
    return steps * step_minutes / 1440


def shift_window(window: TimeWindow, days: float) -> TimeWindow:
    """Return ``window`` moved by ``days`` (positive = later), same step and length."""
    delta = timedelta(days=days)
    return window.model_copy(
        update={"start_utc": window.start_utc + delta, "end_utc": window.end_utc + delta}
    )


def sample_points(
    center: GeoPoint, radius_m: float, rings: int, points_per_ring: int
) -> list[tuple[float, GeoPoint]]:
    """Points on rings around ``center`` (great-circle offsets on the reference sphere).

    Args:
        center: Disk center.
        radius_m: Disk radius, meters; 0 gives no samples.
        rings: Number of rings at radius_m * k / rings, k = 1..rings.
        points_per_ring: Points per ring, azimuths 0, 360/n, ... degrees from north, clockwise.

    Returns:
        (distance from center in meters, point) pairs; the center itself is not included.
    """
    if radius_m <= 0 or rings == 0:
        return []
    out = []
    for k in range(1, rings + 1):
        r = radius_m * k / rings
        for j in range(points_per_ring):
            point = destination(center, r, 360.0 * j / points_per_ring)
            out.append((r, point))
    return out


def destination(start: GeoPoint, distance_m: float, azimuth_deg: float) -> GeoPoint:
    """Point reached from ``start`` along a great circle (spherical Moon, radius 1737.4 km).

    Args:
        start: Starting point (planetocentric latitude, east longitude, degrees).
        distance_m: Distance along the surface, meters.
        azimuth_deg: Initial direction, degrees from north, clockwise.

    Returns:
        The destination, longitude wrapped to [-180, 180), same ``height_m``.
    """
    lat1, lon1 = math.radians(start.lat_deg), math.radians(start.lon_deg)
    az, d = math.radians(azimuth_deg), distance_m / MOON_RADIUS_M
    lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(az))
    lon2 = lon1 + math.atan2(
        math.sin(az) * math.sin(d) * math.cos(lat1), math.cos(d) - math.sin(lat1) * math.sin(lat2)
    )
    lon_deg = (math.degrees(lon2) + 180.0) % 360.0 - 180.0
    return GeoPoint(lat_deg=math.degrees(lat2), lon_deg=lon_deg, height_m=start.height_m)


def summarize(report: RobustnessReport) -> str:
    """Plain-language conclusion quoting only numbers present in ``report`` (MA-3)."""
    n = report.nominal
    parts = [
        f"Nominal window: Sun visible {_pct(n.illumination_fraction)} of the time, Earth visible "
        f"{_pct(n.earth_visibility_fraction)}, longest darkness {_h(n.longest_dark_h)}."
    ]
    shifts = report.date_shifts
    if shifts:
        worst = min(shifts, key=lambda s: s.metrics.illumination_fraction)
        best = max(shifts, key=lambda s: s.metrics.illumination_fraction)
        max_dark = max(s.metrics.longest_dark_h for s in shifts)
        parts.append(
            f"Shifting the dates by {', '.join(_d(s.shift_days) for s in shifts)} days changes "
            f"sunlight from {_pct(worst.metrics.illumination_fraction)} (shift "
            f"{_d(worst.shift_days)} d) to {_pct(best.metrics.illumination_fraction)} (shift "
            f"{_d(best.shift_days)} d); the longest darkness reaches {_h(max_dark)}."
        )
        cycle = [s for s in shifts if abs(s.shift_days - SYNODIC_MONTH_D) < 0.5]
        if cycle:
            c = cycle[0]
            parts.append(
                f"One lunar cycle later ({_d(c.shift_days)} d) sunlight is back at "
                f"{_pct(c.metrics.illumination_fraction)}."
            )
    samples = report.dispersion
    if samples:
        ill = [s.metrics.illumination_fraction for s in samples]
        worst_point = min(samples, key=lambda s: s.metrics.illumination_fraction)
        steepest = max(samples, key=lambda s: s.slope_max_deg)
        parts.append(
            f"Landing anywhere within {max(s.offset_m for s in samples):.0f} m "
            f"({len(samples)} points), sunlight ranges from {_pct(min(ill))} (worst point at "
            f"{worst_point.offset_m:.0f} m) to {_pct(max(ill))}; the steepest landing slope is "
            f"{steepest.slope_max_deg:.1f} deg at {steepest.offset_m:.0f} m."
        )
    # Earth link (Michael's decision): reported when the Earth is not visible all the time.
    cases = [n, *(s.metrics for s in shifts), *(s.metrics for s in samples)]
    if any(m.earth_visibility_fraction < 1.0 for m in cases):
        low = min(cases, key=lambda m: m.earth_visibility_fraction)
        outage = max(m.longest_earth_hidden_h for m in cases)
        parts.append(
            f"Direct-to-Earth link: Earth visible {_pct(n.earth_visibility_fraction)} of the "
            f"nominal window, down to {_pct(low.earth_visibility_fraction)} in the worst case; "
            f"the longest outage is {_h(outage)}."
        )
    return " ".join(parts)


def _pct(fraction: float) -> str:
    return f"{100 * fraction:.0f}%"


def _h(hours: float) -> str:
    return f"{hours:.0f} h"


def _d(days: float) -> str:
    """Signed day count: integers as '+7', others with one decimal as '+29.5'."""
    return f"{days:+.0f}" if abs(days - round(days)) < 1e-9 else f"{days:+.1f}"
