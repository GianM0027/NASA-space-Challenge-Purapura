# ABOUTME: RobustnessAnalyzer (MA-1, MA-2, MA-3): date-slip sweep, dispersion samples, plain summary
# ABOUTME: Implements the MissionAnalyzer port on top of any Evaluator (owner: Michael, D37)

"""Mission analysis: how robust a site is to launch slips and to where exactly the lander lands.

* MA-1: the nominal window shifted by each offset (default +1, +3, +7, +14 days).
* MA-2: points on rings inside the operations-area disk (radius = landing precision + operating
  range), each evaluated over the nominal window; worst case and spread go in the summary.
* MA-3: a plain-language summary that only quotes numbers present in the report.
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
DEFAULT_SHIFTS_DAYS = (1.0, 3.0, 7.0, 14.0)  # spec MA-1
DEFAULT_RINGS = 2  # sample rings at R/2 and R (MA-2)
DEFAULT_POINTS_PER_RING = 4  # north, east, south, west: each sample costs one evaluation


class RobustnessAnalyzer:
    """Evaluates a site's sensitivity to date shifts and landing dispersion.

    Args:
        evaluator: Evaluator used for every case (nominal, shifted windows, sample points).
        rings: Number of sample rings, evenly spaced out to the disk edge.
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
        """Evaluate the nominal case, each date shift and samples of the operations area.

        Args:
            location: Nominal landing point.
            window: Nominal time window.
            area: Operations area; its disk (landing precision + operating range) is sampled.
            shifts_days: Window shifts, days (positive = later); empty means the defaults.
            site_id: Catalog id to echo in the report.

        Returns:
            The robustness report, with a summary quoting only its own numbers.
        """
        nominal = self.evaluator.evaluate(location, window, area, site_id).metrics
        shifts = list(shifts_days) or list(DEFAULT_SHIFTS_DAYS)
        date_shifts = [
            DateShiftResult(
                shift_days=s,
                metrics=self.evaluator.evaluate(location, shift_window(window, s), area).metrics,
            )
            for s in shifts
        ]
        # Each sample asks "what if we land here": its slope is the landing-disk slope there.
        sample_area = area.model_copy(update={"operating_range_m": 0.0})
        dispersion = []
        for offset_m, point in sample_points(
            location,
            area.landing_precision_m + area.operating_range_m,
            self.rings,
            self.points_per_ring,
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
    if report.date_shifts:
        worst = min(report.date_shifts, key=lambda s: s.metrics.illumination_fraction)
        best = max(report.date_shifts, key=lambda s: s.metrics.illumination_fraction)
        max_dark = max(s.metrics.longest_dark_h for s in report.date_shifts)
        parts.append(
            f"Shifting the dates by {_days(report.date_shifts)} changes sunlight from "
            f"{_pct(worst.metrics.illumination_fraction)} (shift {worst.shift_days:+g} d) to "
            f"{_pct(best.metrics.illumination_fraction)} (shift {best.shift_days:+g} d); the "
            f"longest darkness reaches {_h(max_dark)}."
        )
    if report.dispersion:
        ill = [s.metrics.illumination_fraction for s in report.dispersion]
        worst_point = min(report.dispersion, key=lambda s: s.metrics.illumination_fraction)
        steepest = max(report.dispersion, key=lambda s: s.slope_max_deg)
        parts.append(
            f"Across {len(report.dispersion)} points up to "
            f"{max(s.offset_m for s in report.dispersion):.0f} m from the site, sunlight ranges "
            f"from {_pct(min(ill))} (worst point at {worst_point.offset_m:.0f} m) to "
            f"{_pct(max(ill))}; the steepest landing slope is {steepest.slope_max_deg:.1f} deg "
            f"at {steepest.offset_m:.0f} m."
        )
    return " ".join(parts)


def _pct(fraction: float) -> str:
    return f"{100 * fraction:.0f}%"


def _h(hours: float) -> str:
    return f"{hours:.0f} h"


def _days(shifts: list[DateShiftResult]) -> str:
    return ", ".join(f"{s.shift_days:+g}" for s in shifts) + " days"
