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
    longest_run,
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
            area: Operations area, passed to the terrain provider (observer height for the
                horizon; landing disk, full disk and reachable share for the terrain, EVA-2).
            site_id: Catalog id to echo in the result, if the point is a catalog site.

        Returns:
            The full evaluation.

        Raises:
            ValueError: If the ephemeris returns no samples.
        """
        series = self._ephemeris.sun_earth(location, window)
        if not series.times_utc:
            raise ValueError(f"ephemeris returned no samples for {window}")
        horizon = self._terrain.horizon_mask(location, area)
        terrain = self._terrain.terrain_stats(location, area)

        mask_az = np.asarray(horizon.azimuth_deg)
        mask_el = np.asarray(horizon.horizon_elevation_deg)
        sun_el = np.asarray(series.sun_elevation_deg)
        earth_el = np.asarray(series.earth_elevation_deg)
        # The interpolated horizon is both the visibility threshold and an output (decision D29),
        # so the UI timeline draws exactly the line the engine compared against.
        sun_horizon = horizon_at(mask_az, mask_el, np.asarray(series.sun_azimuth_deg))
        earth_horizon = horizon_at(mask_az, mask_el, np.asarray(series.earth_azimuth_deg))
        sun_vis = is_visible(sun_el, sun_horizon)
        earth_vis = is_visible(earth_el, earth_horizon)
        metrics = compute_metrics(series.times_utc, sun_el, sun_vis, earth_el, earth_vis, window)

        return Evaluation(
            site_id=site_id,
            location=location,
            window=window,
            area=area,
            times_utc=series.times_utc,
            sun_azimuth_deg=series.sun_azimuth_deg,
            sun_elevation_deg=series.sun_elevation_deg,
            sun_horizon_elevation_deg=sun_horizon.tolist(),
            sun_visible=sun_vis.tolist(),
            earth_azimuth_deg=series.earth_azimuth_deg,
            earth_elevation_deg=series.earth_elevation_deg,
            earth_horizon_elevation_deg=earth_horizon.tolist(),
            earth_visible=earth_vis.tolist(),
            horizon=horizon,
            terrain=terrain,
            metrics=metrics,
        )


def compute_metrics(
    times,
    sun_el: np.ndarray,
    sun_vis: np.ndarray,
    earth_el: np.ndarray,
    earth_vis: np.ndarray,
    window: TimeWindow,
) -> VisibilityMetrics:
    """Power and communication metrics from per-sample visibility (decisions D20 and D29).

    Args:
        times: Sample times (list of aware datetimes).
        sun_el: Geometric Sun elevation per sample, degrees.
        sun_vis: Sun visible per sample.
        earth_el: Geometric Earth elevation per sample, degrees.
        earth_vis: Earth visible per sample.
        window: The window; ``step_minutes`` is the duration of one sample.

    Returns:
        The metrics.
    """
    step_h = window.step_minutes / 60.0
    lit = sun_el[sun_vis]
    in_view = earth_el[earth_vis]
    light_h, light_cut = longest_run(sun_vis, True, step_h)
    dark_h, dark_cut = longest_run(sun_vis, False, step_h)
    contact_h, contact_cut = longest_run(earth_vis, True, step_h)
    outage_h, outage_cut = longest_run(earth_vis, False, step_h)
    return VisibilityMetrics(
        illumination_fraction=float(sun_vis.mean()),
        sun_elevation_max_deg=float(sun_el.max()),
        sun_elevation_mean_visible_deg=float(lit.mean()) if lit.size else None,
        longest_light_h=light_h,
        longest_light_truncated=light_cut,
        longest_dark_h=dark_h,
        longest_dark_truncated=dark_cut,
        earth_visibility_fraction=float(earth_vis.mean()),
        earth_elevation_mean_visible_deg=float(in_view.mean()) if in_view.size else None,
        longest_earth_visible_h=contact_h,
        longest_earth_visible_truncated=contact_cut,
        longest_earth_hidden_h=outage_h,
        longest_earth_hidden_truncated=outage_cut,
        sun_and_earth_visible_fraction=float((sun_vis & earth_vis).mean()),
        sun_visible_at_start=bool(sun_vis[0]),
        earth_visible_at_start=bool(earth_vis[0]),
        next_sunset_utc=first_transition(times, sun_vis, False),
        next_sunrise_utc=first_transition(times, sun_vis, True),
        next_earthset_utc=first_transition(times, earth_vis, False),
        next_earthrise_utc=first_transition(times, earth_vis, True),
    )
