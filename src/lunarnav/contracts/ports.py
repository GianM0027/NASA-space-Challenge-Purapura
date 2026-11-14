# ABOUTME: Interfaces (Protocols) every LunarNav module implements; the API wires them together
# ABOUTME: Owner: Gian. Implementations never import each other's internals

"""Ports between LunarNav modules.

Each module provides one class implementing its Protocol, and exposes a factory function from
its package ``__init__`` so that ``lunarnav.api`` can find and wire it without being edited
(spec IF-5, names listed in ``lunarnav.api.wiring``):

* ``lunarnav.catalog.build_catalog() -> SiteCatalog``
* ``lunarnav.ephemeris.build_ephemeris_provider() -> EphemerisProvider``
* ``lunarnav.terrain.build_terrain_provider() -> TerrainProvider``
* ``lunarnav.evaluation.build_evaluator(ephemeris, terrain) -> Evaluator``
* ``lunarnav.mission_analysis.build_mission_analyzer(evaluator) -> MissionAnalyzer``

A factory takes its upstream dependencies as arguments (it never builds another module's
classes itself) and reads its own configuration (data paths, cache folders) on its own.
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

    def horizon_mask(self, location: GeoPoint, area: OperationsArea) -> HorizonMask:
        """Return the terrain horizon elevation around ``location`` as a function of azimuth.

        Args:
            location: Observer on the Moon. An absolute ``height_m`` is the observer height;
                without it the observer stands ``area.observer_height_above_ground_m`` above
                the terrain.
            area: Operations area; only its observer height is used.

        Returns:
            The horizon mask.
        """
        ...

    def terrain_stats(self, location: GeoPoint, area: OperationsArea) -> TerrainStats:
        """Return elevation, slope and reachability statistics over the operations area.

        Args:
            location: Center of the operations area.
            area: Landing precision, operating range and traverse slope limit.

        Returns:
            The terrain statistics (see ``TerrainStats`` for the two disks).
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
