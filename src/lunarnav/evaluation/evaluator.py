# ABOUTME: LunarEvaluator: the Evaluator port; ephemerides + horizon mask + terrain -> Evaluation
# ABOUTME: EVA-1 (visibility series and metrics) and EVA-2 (terrain over the operations disk)

"""Evaluator implementation: combines an ephemeris provider and a terrain provider."""

from __future__ import annotations

import numpy as np

from lunarnav.contracts import (
    EphemerisProvider,
    Evaluation,
    GeoPoint,
    OperationsArea,
    TerrainProvider,
    TimeWindow,
    VisibilityMetrics,
)
from lunarnav.evaluation.visibility import (
    first_transition,
    horizon_at,
    is_visible,
    longest_run_h,
)


class LunarEvaluator:
    """Evaluates one lunar point over one time window.

    Args:
        ephemeris: Source of topocentric Sun and Earth directions.
        terrain: Source of the horizon mask and terrain statistics.
    """

    def __init__(self, ephemeris: EphemerisProvider, terrain: TerrainProvider):
        """See the class docstring."""
        self._ephemeris = ephemeris
        self._terrain = terrain

    def evaluate(
        self,
        location: GeoPoint,
        window: TimeWindow,
        area: OperationsArea,
        site_id: str | None = None,
    ) -> Evaluation:
        """Evaluate one point over one window.

        Args:
            location: Point to evaluate.
            window: Time window; its step is the duration of one sample.
            area: Operations area; terrain statistics cover the disk of radius
                ``landing_precision_m + operating_range_m`` (EVA-2).
            site_id: Catalog id to echo in the result, if the point is a catalog site.

        Returns:
            The full evaluation.

        Raises:
            ValueError: If the ephemeris returns no samples.
        """
        series = self._ephemeris.sun_earth(location, window)
        if not series.times_utc:
            raise ValueError(f"ephemeris returned no samples for {window}")
        horizon = self._terrain.horizon_mask(location)
        radius_m = area.landing_precision_m + area.operating_range_m
        terrain = self._terrain.terrain_stats(location, radius_m)

        mask_az = np.asarray(horizon.azimuth_deg)
        mask_el = np.asarray(horizon.horizon_elevation_deg)
        sun_el = np.asarray(series.sun_elevation_deg)
        earth_el = np.asarray(series.earth_elevation_deg)
        sun_vis = is_visible(
            sun_el, horizon_at(mask_az, mask_el, np.asarray(series.sun_azimuth_deg))
        )
        earth_vis = is_visible(
            earth_el, horizon_at(mask_az, mask_el, np.asarray(series.earth_azimuth_deg))
        )
        metrics = compute_metrics(series.times_utc, sun_el, sun_vis, earth_vis, window)

        return Evaluation(
            site_id=site_id,
            location=location,
            window=window,
            area=area,
            times_utc=series.times_utc,
            sun_azimuth_deg=series.sun_azimuth_deg,
            sun_elevation_deg=series.sun_elevation_deg,
            sun_visible=sun_vis.tolist(),
            earth_azimuth_deg=series.earth_azimuth_deg,
            earth_elevation_deg=series.earth_elevation_deg,
            earth_visible=earth_vis.tolist(),
            horizon=horizon,
            terrain=terrain,
            metrics=metrics,
        )


def compute_metrics(
    times, sun_el: np.ndarray, sun_vis: np.ndarray, earth_vis: np.ndarray, window: TimeWindow
) -> VisibilityMetrics:
    """Power and communication metrics from per-sample visibility (definitions of decision D20).

    Args:
        times: Sample times (list of aware datetimes).
        sun_el: Geometric Sun elevation per sample, degrees.
        sun_vis: Sun visible per sample.
        earth_vis: Earth visible per sample.
        window: The window; ``step_minutes`` is the duration of one sample.

    Returns:
        The metrics.
    """
    step_h = window.step_minutes / 60.0
    lit = sun_el[sun_vis]
    return VisibilityMetrics(
        illumination_fraction=float(sun_vis.mean()),
        sun_elevation_max_deg=float(sun_el.max()),
        sun_elevation_mean_visible_deg=float(lit.mean()) if lit.size else None,
        longest_light_h=longest_run_h(sun_vis, True, step_h),
        longest_dark_h=longest_run_h(sun_vis, False, step_h),
        earth_visibility_fraction=float(earth_vis.mean()),
        longest_earth_visible_h=longest_run_h(earth_vis, True, step_h),
        longest_earth_hidden_h=longest_run_h(earth_vis, False, step_h),
        sun_visible_at_start=bool(sun_vis[0]),
        earth_visible_at_start=bool(earth_vis[0]),
        next_sunset_utc=first_transition(times, sun_vis, False),
        next_sunrise_utc=first_transition(times, sun_vis, True),
        next_earthset_utc=first_transition(times, earth_vis, False),
        next_earthrise_utc=first_transition(times, earth_vis, True),
    )
