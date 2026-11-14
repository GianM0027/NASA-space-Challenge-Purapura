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

from lunarnav.contracts import (
    AiAnswer,
    EphemerisProvider,
    EphemerisSeries,
    Evaluation,
    Evaluator,
    GeoPoint,
    HorizonMask,
    MissionAnalyzer,
    MissionRequirements,
    OperationsArea,
    RobustnessReport,
    Site,
    SiteCatalog,
    SiteRanking,
    TerrainProvider,
    TerrainStats,
    TimeWindow,
    VisibilityMetrics,
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
    """Natural-language request to requirements plus ranking (spec AI-1)."""

    def ask(self, text: str) -> AiAnswer:
        """Answer a natural-language mission request."""
        ...


@dataclass(frozen=True)
class Services:
    """Everything the API needs, built once by the composition root.

    Attributes:
        catalog: Site catalog.
        evaluator: Site evaluation engine.
        analyzer: Mission analysis.
        ranker: Deterministic ranking.
        assistant: AI assistant.
    """

    catalog: SiteCatalog
    evaluator: Evaluator
    analyzer: MissionAnalyzer
    ranker: Ranker
    assistant: Assistant


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

    def horizon_mask(self, location: GeoPoint) -> HorizonMask:
        """Return a flat (0 degree) horizon at 1 degree azimuth steps."""
        return HorizonMask(
            location=location,
            azimuth_deg=[float(a) for a in range(360)],
            horizon_elevation_deg=[0.0] * 360,
            dem_source=SYNTHETIC,
            dem_resolution_m=self._stats.dem_resolution_m,
            max_distance_m=1.0,
        )

    def terrain_stats(self, location: GeoPoint, radius_m: float) -> TerrainStats:
        """Return the example statistics relabelled with ``location`` and ``radius_m``."""
        return self._stats.model_copy(
            update={"location": location, "radius_m": radius_m, "dem_source": SYNTHETIC}
        )


def _longest_run_h(flags: list[bool], state: bool, step_h: float) -> float:
    """Return the longest run of ``state`` in ``flags``, hours (n samples last n * step)."""
    best = current = 0
    for flag in flags:
        current = current + 1 if flag is state else 0
        best = max(best, current)
    return best * step_h


def _first_transition(times: list[datetime], flags: list[bool], to: bool) -> datetime | None:
    """Return the time of the first sample entering state ``to`` after the start, or None."""
    for i in range(1, len(flags)):
        if flags[i] is to and flags[i - 1] is not to:
            return times[i]
    return None


class ExampleEvaluator:
    """Placeholder evaluator: body visible when its elevation exceeds the horizon at azimuth 0.

    It ignores the azimuth dependence of the mask (it is only ever paired with flat placeholder
    terrain or used to draw curves); the real evaluator is Federico's (spec EVA-1).
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
        """Evaluate ``location`` over ``window`` with the placeholder visibility rule."""
        series = self._ephemeris.sun_earth(location, window)
        horizon = self._terrain.horizon_mask(location)
        level = horizon.horizon_elevation_deg[0]
        times = series.times_utc
        sun_visible = [el > level for el in series.sun_elevation_deg]
        earth_visible = [el > level for el in series.earth_elevation_deg]
        step_h = window.step_minutes / 60.0
        lit = [el for el, vis in zip(series.sun_elevation_deg, sun_visible, strict=True) if vis]
        metrics = VisibilityMetrics(
            illumination_fraction=sum(sun_visible) / len(times),
            sun_elevation_max_deg=max(series.sun_elevation_deg),
            sun_elevation_mean_visible_deg=sum(lit) / len(lit) if lit else None,
            longest_light_h=_longest_run_h(sun_visible, True, step_h),
            longest_dark_h=_longest_run_h(sun_visible, False, step_h),
            earth_visibility_fraction=sum(earth_visible) / len(times),
            longest_earth_visible_h=_longest_run_h(earth_visible, True, step_h),
            longest_earth_hidden_h=_longest_run_h(earth_visible, False, step_h),
            sun_visible_at_start=sun_visible[0],
            earth_visible_at_start=earth_visible[0],
            next_sunset_utc=_first_transition(times, sun_visible, False),
            next_sunrise_utc=_first_transition(times, sun_visible, True),
            next_earthset_utc=_first_transition(times, earth_visible, False),
            next_earthrise_utc=_first_transition(times, earth_visible, True),
        )
        radius = area.landing_precision_m + area.operating_range_m
        return Evaluation(
            site_id=site_id,
            location=location,
            window=window,
            area=area,
            times_utc=times,
            sun_azimuth_deg=series.sun_azimuth_deg,
            sun_elevation_deg=series.sun_elevation_deg,
            sun_visible=sun_visible,
            earth_azimuth_deg=series.earth_azimuth_deg,
            earth_elevation_deg=series.earth_elevation_deg,
            earth_visible=earth_visible,
            horizon=horizon,
            terrain=self._terrain.terrain_stats(location, radius),
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
        raise KeyError(site_id)

    def add_user_site(self, site: Site) -> Site:
        """Add a site in memory.

        Raises:
            ValueError: If the id already exists.
        """
        if any(existing.id == site.id for existing in self._sites):
            raise ValueError(f"site id {site.id!r} already exists")
        self._sites.append(site)
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

    def ask(self, text: str) -> AiAnswer:
        """Return the example answer, with ``source_request`` set to ``text``."""
        requirements = self._example.requirements.model_copy(update={"source_request": text})
        return self._example.model_copy(update={"requirements": requirements})
