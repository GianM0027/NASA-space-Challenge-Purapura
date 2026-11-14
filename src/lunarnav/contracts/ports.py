# ABOUTME: Interfaces (Protocols) every LunarNav module implements; the API wires them together
# ABOUTME: Owner: Gian. Implementations never import each other's internals

"""Ports between LunarNav modules.

Each module provides one class implementing its Protocol. ``lunarnav.api`` builds the concrete
objects and injects them (e.g. the evaluator receives an ephemeris provider and a terrain provider).
"""

from __future__ import annotations

from typing import Protocol

from lunarnav.contracts.models import (
    EphemerisSeries,
    Evaluation,
    GeoPoint,
    HorizonMask,
    OperationsArea,
    RobustnessReport,
    Site,
    TerrainStats,
    TimeWindow,
)


class EphemerisProvider(Protocol):
    """Sun and Earth directions seen from a lunar surface point (owner: Michael)."""

    def sun_earth(self, location: GeoPoint, window: TimeWindow) -> EphemerisSeries:
        """Return topocentric Sun and Earth azimuth/elevation over the window.

        Args:
            location: Observer on the Moon.
            window: Times to sample.

        Returns:
            Geometric directions (no terrain), aligned with the window's sample times.
        """
        ...


class TerrainProvider(Protocol):
    """Terrain horizon and slopes from LOLA topography (owner: Federico)."""

    def horizon_mask(self, location: GeoPoint) -> HorizonMask:
        """Return the terrain horizon elevation around ``location`` as a function of azimuth.

        Args:
            location: Observer on the Moon.

        Returns:
            The horizon mask.
        """
        ...

    def terrain_stats(self, location: GeoPoint, radius_m: float) -> TerrainStats:
        """Return elevation and slope statistics over a disk.

        Args:
            location: Disk center.
            radius_m: Disk radius, meters, >= 0.

        Returns:
            The terrain statistics.
        """
        ...


class Evaluator(Protocol):
    """Combines ephemerides and terrain into visibility series and metrics (owner: Federico)."""

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
            window: Time window.
            area: Operations area for terrain statistics.
            site_id: Catalog id to echo in the result, if the point is a catalog site.

        Returns:
            The full evaluation.
        """
        ...


class SiteCatalog(Protocol):
    """Access to the site catalog (owner: Michael)."""

    def list_sites(self) -> list[Site]:
        """Return all sites, curated first, then user-added ones."""
        ...

    def get_site(self, site_id: str) -> Site:
        """Return the site with id ``site_id``.

        Raises:
            KeyError: If no site has that id.
        """
        ...

    def add_user_site(self, site: Site) -> Site:
        """Persist a user-defined site and return it.

        Raises:
            ValueError: If the id already exists.
        """
        ...


class MissionAnalyzer(Protocol):
    """Robustness of a site to date slips and landing dispersion (owner: Gian)."""

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
            area: Landing precision and operating range defining the sampled disk.
            shifts_days: Window shifts to evaluate, days (positive = later).
            site_id: Catalog id to echo in the report.

        Returns:
            The robustness report.
        """
        ...
