# ABOUTME: API service ports (ranking, AI) and placeholders used until the real modules exist
# ABOUTME: Owner: Gian; wiring.py swaps each placeholder for the real module (spec IF-5)

"""Service ports used by the API, plus placeholder implementations.

The placeholders let the frontend and each engine module be developed and *seen* before the
others exist (spec IF-2). They are labelled "SYNTHETIC" in every provenance field and are never
used once the real module provides its factory (spec IF-5).

The placeholder ephemeris is a toy model, good enough to draw plausible curves and nothing else:
Sun and Earth are treated as infinitely far, the sub-Earth point is fixed at (0, 0) (no
libration), the subsolar point runs along the equator once per synodic month (no axial tilt)
with an arbitrary phase. Do not validate anything against it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from pydantic import TypeAdapter

from lunarnav.api.placeholder_metrics import compute_metrics, horizon_at
from lunarnav.contracts import (
    AiAnswer,
    AiRequest,
    DuplicateSiteError,
    EphemerisProvider,
    EphemerisSeries,
    Evaluation,
    Evaluator,
    GeoPoint,
    HorizonMask,
    MissionAnalyzer,
    MissionRequirements,
    OperationsArea,
    Origin,
    ReadOnlySiteError,
    RobustnessReport,
    Site,
    SiteCatalog,
    SiteRanking,
    TerrainProvider,
    TerrainStats,
    TimeWindow,
    TradeoffAnalyzer,
    TradeoffResult,
    TradeoffSettings,
    UnknownSiteError,
)

EXAMPLES_DIR = Path(__file__).resolve().parents[3] / "data" / "examples"
SYNTHETIC = "SYNTHETIC placeholder, not real data"

# Mean synodic month, days (Explanatory Supplement to the Astronomical Almanac, 3rd ed., 2012).
SYNODIC_MONTH_DAYS = 29.530589
# Arbitrary epoch fixing the phase of the toy subsolar longitude; has no physical meaning.
_TOY_EPOCH = datetime(2000, 1, 1, tzinfo=UTC)


class Ranker(Protocol):
    """Deterministic ranking of catalog sites against mission requirements (spec AI-2)."""

    def rank(self, requirements: MissionRequirements) -> SiteRanking:
        """Rank catalog sites; best first."""
        ...


class Assistant(Protocol):
    """Chat turn to requirements plus ranking (spec AI-1), and explanations (spec AI-3)."""

    def ask(self, request: AiRequest) -> AiAnswer:
        """Answer one chat turn with updated requirements and, when possible, a ranking."""
        ...

    def explain(self, ranking: SiteRanking, language_hint: str = "") -> SiteRanking:
        """Return ``ranking`` with a short rationale on every result."""
        ...

    def comment_analysis(
        self, report: RobustnessReport, site_name: str, language_hint: str = ""
    ) -> RobustnessReport:
        """Return ``report`` with a short checked AI comment (spec AI-6)."""
        ...

    def comment_tradeoff(self, result: TradeoffResult, language_hint: str = "") -> TradeoffResult:
        """Return ``result`` with a short checked AI comment (spec TO-5)."""
        ...


@dataclass(frozen=True)
class Services:
    """Everything the API needs, built once by the composition root.

    Attributes:
        catalog: Site catalog.
        ephemeris: Sun and Earth directions (also lights the globe).
        evaluator: Site evaluation engine.
        analyzer: Mission analysis.
        ranker: Deterministic ranking.
        assistant: AI assistant.
        tradeoff: AHP trade-off over compared scenarios (spec section 4.8).
    """

    catalog: SiteCatalog
    ephemeris: EphemerisProvider
    evaluator: Evaluator
    analyzer: MissionAnalyzer
    ranker: Ranker
    assistant: Assistant
    tradeoff: TradeoffAnalyzer


def _read(name: str) -> str:
    """Return the text of one example payload."""
    return (EXAMPLES_DIR / name).read_text(encoding="utf-8")


def sample_times(window: TimeWindow) -> list[datetime]:
    """Return the sample times of a window: start, start + step, ... up to end inclusive.

    Args:
        window: The time window.

    Returns:
        Timezone-aware sample times, at least one.
    """
    step = timedelta(minutes=window.step_minutes)
    count = int((window.end_utc - window.start_utc) / step) + 1
    return [window.start_utc + i * step for i in range(count)]


def _direction(lat_deg: float, lon_deg: float, sub_lon_deg: float) -> tuple[float, float]:
    """Return azimuth and elevation of a far body whose sub-point is on the equator.

    Args:
        lat_deg: Observer latitude, degrees.
        lon_deg: Observer east longitude, degrees.
        sub_lon_deg: East longitude of the point where the body is at the zenith, degrees.

    Returns:
        (azimuth from north clockwise in [0, 360), elevation), degrees.
    """
    lat = math.radians(lat_deg)
    dlon = math.radians(sub_lon_deg - lon_deg)
    # Elevation of an infinitely far body = 90 deg minus the great-circle distance to its sub-point.
    elevation = math.degrees(math.asin(math.cos(lat) * math.cos(dlon)))
    # Initial great-circle bearing from the observer to the sub-point (latitude 0).
    azimuth = math.degrees(math.atan2(math.sin(dlon), -math.sin(lat) * math.cos(dlon)))
    return azimuth % 360.0, elevation


class ExampleEphemerisProvider:
    """Toy Sun and Earth directions aligned with the requested window (see module docstring)."""

    def sun_earth(self, location: GeoPoint, window: TimeWindow) -> EphemerisSeries:
        """Return toy-model Sun and Earth directions at the window's sample times."""
        times = sample_times(window)
        earth_az, earth_el = _direction(location.lat_deg, location.lon_deg, 0.0)
        sun: list[tuple[float, float]] = []
        for time in times:
            days = (time - _TOY_EPOCH).total_seconds() / 86400.0
            # The subsolar point moves westward by 360 deg per synodic month.
            sub_lon = -360.0 * (days / SYNODIC_MONTH_DAYS)
            sun.append(_direction(location.lat_deg, location.lon_deg, sub_lon))
        return EphemerisSeries(
            location=location,
            times_utc=times,
            sun_azimuth_deg=[az for az, _ in sun],
            sun_elevation_deg=[el for _, el in sun],
            earth_azimuth_deg=[earth_az] * len(times),
            earth_elevation_deg=[earth_el] * len(times),
            source=SYNTHETIC,
        )


class ExampleTerrainProvider:
    """Flat terrain: a zero horizon everywhere and the example slope statistics."""

    def __init__(self) -> None:
        """Load the example terrain statistics."""
        self._stats = TerrainStats.model_validate_json(_read("terrain_stats.json"))

    def horizon_mask(self, location: GeoPoint, area: OperationsArea) -> HorizonMask:
        """Return a flat (0 degree) horizon at 1 degree azimuth steps, whatever the height."""
        return HorizonMask(
            location=location,
            azimuth_deg=[float(a) for a in range(360)],
            horizon_elevation_deg=[0.0] * 360,
            dem_source=SYNTHETIC,
            dem_resolution_m=self._stats.dem_resolution_m,
            max_distance_m=1.0,
        )

    def terrain_stats(self, location: GeoPoint, area: OperationsArea) -> TerrainStats:
        """Return the example slopes relabelled with ``location`` and the radii of ``area``."""
        reachable = self._stats.reachable_fraction if area.operating_range_m > 0.0 else None
        return self._stats.model_copy(
            update={
                "location": location,
                "radius_m": area.landing_precision_m + area.operating_range_m,
                "landing_radius_m": area.landing_precision_m,
                "traverse_slope_limit_deg": area.traverse_slope_limit_deg,
                "reachable_fraction": reachable,
                "dem_source": SYNTHETIC,
            }
        )


class ExampleEvaluator:
    """Placeholder evaluator: the spec section 3 definitions applied in plain Python.

    It interpolates the horizon mask at each body's azimuth, so paired with the real ephemeris
    and terrain modules it already gives meaningful numbers; the real, faster evaluator is
    Federico's (spec EVA-1).
    """

    def __init__(self, ephemeris: EphemerisProvider, terrain: TerrainProvider) -> None:
        """Store the providers.

        Args:
            ephemeris: Source of Sun and Earth directions.
            terrain: Source of the horizon mask and terrain statistics.
        """
        self._ephemeris = ephemeris
        self._terrain = terrain

    def evaluate(
        self,
        location: GeoPoint,
        window: TimeWindow,
        area: OperationsArea,
        site_id: str | None = None,
    ) -> Evaluation:
        """Evaluate ``location`` over ``window``."""
        series = self._ephemeris.sun_earth(location, window)
        horizon = self._terrain.horizon_mask(location, area)

        def mask(azimuths: list[float]) -> list[float]:
            """Horizon elevation at each azimuth."""
            return [
                horizon_at(horizon.azimuth_deg, horizon.horizon_elevation_deg, a) for a in azimuths
            ]

        sun_horizon = mask(series.sun_azimuth_deg)
        earth_horizon = mask(series.earth_azimuth_deg)
        sun_visible = [el > h for el, h in zip(series.sun_elevation_deg, sun_horizon, strict=True)]
        earth_visible = [
            el > h for el, h in zip(series.earth_elevation_deg, earth_horizon, strict=True)
        ]
        metrics = compute_metrics(
            series.times_utc,
            series.sun_elevation_deg,
            sun_visible,
            series.earth_elevation_deg,
            earth_visible,
            window.step_minutes / 60.0,
        )
        return Evaluation(
            site_id=site_id,
            location=location,
            window=window,
            area=area,
            times_utc=series.times_utc,
            sun_azimuth_deg=series.sun_azimuth_deg,
            sun_elevation_deg=series.sun_elevation_deg,
            sun_horizon_elevation_deg=sun_horizon,
            sun_visible=sun_visible,
            earth_azimuth_deg=series.earth_azimuth_deg,
            earth_elevation_deg=series.earth_elevation_deg,
            earth_horizon_elevation_deg=earth_horizon,
            earth_visible=earth_visible,
            horizon=horizon,
            terrain=self._terrain.terrain_stats(location, area),
            metrics=metrics,
        )


class ExampleCatalog:
    """In-memory catalog seeded from ``data/examples/sites.json``; user sites are not persisted."""

    def __init__(self) -> None:
        """Load the example sites."""
        self._sites = TypeAdapter(list[Site]).validate_json(_read("sites.json"))

    def list_sites(self) -> list[Site]:
        """Return all sites in insertion order."""
        return list(self._sites)

    def get_site(self, site_id: str) -> Site:
        """Return the site with id ``site_id``.

        Raises:
            KeyError: If no site has that id.
        """
        for site in self._sites:
            if site.id == site_id:
                return site
        raise UnknownSiteError(site_id)

    def add_user_site(self, site: Site) -> Site:
        """Add a site in memory.

        Raises:
            DuplicateSiteError: If the id already exists.
        """
        if any(existing.id == site.id for existing in self._sites):
            raise DuplicateSiteError(f"site id {site.id!r} already exists")
        self._sites.append(site)
        return site

    def remove_user_site(self, site_id: str) -> None:
        """Delete a user site from memory.

        Raises:
            UnknownSiteError: If no site has that id.
            ReadOnlySiteError: If the site is not a user site.
        """
        self._sites.remove(self._user_site(site_id))

    def rename_user_site(self, site_id: str, name: str) -> Site:
        """Rename a user site in memory; the id stays the same.

        Raises:
            UnknownSiteError: If no site has that id.
            ReadOnlySiteError: If the site is not a user site.
            ValueError: If ``name`` is empty after stripping.
        """
        return self.update_user_site(site_id, name=name)

    def update_user_site(
        self, site_id: str, *, name: str | None = None, description: str | None = None
    ) -> Site:
        """Change the name and/or description of a user site in memory; the id stays the same.

        Args:
            site_id: Id of the site to edit.
            name: New display name, stripped; None keeps the current one.
            description: New description, stripped; None keeps it, "" clears it.

        Returns:
            The updated site.

        Raises:
            UnknownSiteError: If no site has that id.
            ReadOnlySiteError: If the site is not a user site.
            ValueError: If ``name`` is given but empty after stripping.
        """
        site = self._user_site(site_id)
        update: dict[str, str] = {}
        if name is not None:
            if not name.strip():
                raise ValueError("site name must not be empty")
            update["name"] = name.strip()
        if description is not None:
            update["description"] = description.strip()
        edited = site.model_copy(update=update)
        self._sites[self._sites.index(site)] = edited
        return edited

    def _user_site(self, site_id: str) -> Site:
        """Return the site with id ``site_id`` if it may be changed.

        Raises:
            UnknownSiteError: If no site has that id.
            ReadOnlySiteError: If the site is not a user site.
        """
        site = self.get_site(site_id)
        if site.origin is not Origin.USER:
            raise ReadOnlySiteError(f"site {site_id!r} is curated and cannot be changed")
        return site


class ExampleAnalyzer:
    """Returns the example robustness report, relabelled with the requested site id."""

    def __init__(self) -> None:
        """Load the example report."""
        self._example = RobustnessReport.model_validate_json(_read("robustness_report.json"))

    def analyze(
        self,
        location: GeoPoint,
        window: TimeWindow,
        area: OperationsArea,
        shifts_days: list[float],
        site_id: str | None = None,
    ) -> RobustnessReport:
        """Return the example report with ``site_id`` replaced."""
        return self._example.model_copy(update={"site_id": site_id})


class ExampleTradeoff:
    """Stands in for the trade-off module: echoes the labels and computes nothing.

    It has no ``export_xlsx``: the API answers 501 for the export until the real module exists.
    """

    def analyze(self, evaluations: list[Evaluation], settings: TradeoffSettings) -> TradeoffResult:
        """Return an empty result in the scenario order, marked as a placeholder."""
        count = len(settings.labels)
        return TradeoffResult(
            labels=settings.labels,
            foms=[],
            weights={},
            weight_method="default",
            judgments=[],
            consistency_ratio=None,
            table=[{} for _ in range(count)],
            scores=[0.0] * count,
            ranking=list(range(count)),
            method="Placeholder: the trade-off module is not wired yet; nothing is scored.",
        )


class ExampleRanker:
    """Returns the example ranking with the requested requirements echoed back."""

    def __init__(self) -> None:
        """Load the example ranking."""
        self._example = SiteRanking.model_validate_json(_read("site_ranking.json"))

    def rank(self, requirements: MissionRequirements) -> SiteRanking:
        """Return the example ranking for ``requirements``."""
        return self._example.model_copy(update={"requirements": requirements})


class ExampleAssistant:
    """Returns the example AI answer with the request text recorded."""

    def __init__(self) -> None:
        """Load the example answer."""
        self._example = AiAnswer.model_validate_json(_read("ai_answer.json"))

    def ask(self, request: AiRequest) -> AiAnswer:
        """Return the example answer, with ``source_request`` set to the request text."""
        requirements = self._example.requirements.model_copy(
            update={"source_request": request.text}
        )
        return self._example.model_copy(update={"requirements": requirements})

    def explain(self, ranking: SiteRanking, language_hint: str = "") -> SiteRanking:
        """Return ``ranking`` with a fixed example rationale on every result."""
        results = [
            score.model_copy(update={"rationale": "Example explanation (no LLM)."})
            for score in ranking.results
        ]
        return ranking.model_copy(update={"results": results})

    def comment_analysis(
        self, report: RobustnessReport, site_name: str, language_hint: str = ""
    ) -> RobustnessReport:
        """Return ``report`` with a fixed example comment (no LLM)."""
        return report.model_copy(update={"ai_comment": "Example comment (no LLM)."})

    def comment_tradeoff(self, result: TradeoffResult, language_hint: str = "") -> TradeoffResult:
        """Return ``result`` with a fixed example comment (no LLM)."""
        return result.model_copy(update={"ai_comment": "Example comment (no LLM)."})
