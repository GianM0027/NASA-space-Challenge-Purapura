# ABOUTME: Shared data models exchanged between LunarNav modules (catalog, ephemeris, terrain, AI)
# ABOUTME: Owner: Gian. Units: degrees, meters, hours, UTC; changes follow MISSION.md section 6

"""Contract data models for LunarNav.

Conventions shared by every model (see also CLAUDE.md, Domain conventions):

* Angles in degrees, distances in meters, durations in hours, times timezone-aware UTC.
* Selenographic coordinates: planetocentric latitude, east-positive longitude in [-180, 180),
  Moon Mean Earth / polar axis frame, reference sphere radius 1737.4 km.
* Azimuth from local north, clockwise (east = 90), in [0, 360).
* Elevation above the local horizontal plane of the reference sphere. Ephemeris elevations are
  geometric (no terrain); terrain enters only through ``HorizonMask``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class _Contract(BaseModel):
    """Base class of every contract model: unknown fields are rejected, instances are immutable."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _check_same_length(model: BaseModel, *names: str) -> None:
    """Raise if the named list fields of ``model`` do not all have the same length.

    Args:
        model: The model instance being validated.
        *names: Names of list-valued fields that must be aligned element by element.

    Raises:
        ValueError: If the lengths differ.
    """
    lengths = {name: len(getattr(model, name)) for name in names}
    if len(set(lengths.values())) > 1:
        raise ValueError(f"aligned series must have equal length, got {lengths}")


# --- Places and time -------------------------------------------------------------------------


class GeoPoint(_Contract):
    """A point on the lunar surface.

    Attributes:
        lat_deg: Planetocentric latitude, degrees, [-90, 90].
        lon_deg: East-positive longitude, degrees, [-180, 180).
        height_m: Height above the 1737.4 km reference sphere, meters. None means
            "take it from the DEM".
    """

    lat_deg: float = Field(ge=-90.0, le=90.0)
    lon_deg: float = Field(ge=-180.0, lt=180.0)
    height_m: float | None = None


class TimeWindow(_Contract):
    """A UTC time interval sampled at a fixed step.

    Attributes:
        start_utc: First sample, timezone-aware. Also the reference time for "time to next sunset".
        end_utc: Last sample (inclusive when it falls on the step grid); after ``start_utc``.
        step_minutes: Sampling step, whole minutes, >= 1 (JPL Horizons takes no fractions).
    """

    start_utc: AwareDatetime
    end_utc: AwareDatetime
    step_minutes: int = Field(default=60, ge=1)

    @model_validator(mode="after")
    def _end_after_start(self) -> Self:
        """Reject windows whose end is not after their start."""
        if self.end_utc <= self.start_utc:
            raise ValueError(f"end_utc {self.end_utc} must be after start_utc {self.start_utc}")
        return self


class OperationsArea(_Contract):
    """The surface area a mission must be able to use around a nominal site.

    The evaluated disk has radius ``landing_precision_m + operating_range_m``.

    Attributes:
        landing_precision_m: Radius of the landing dispersion (e.g. 3-sigma), meters, >= 0.
        operating_range_m: Radius the rover/crew operates in after landing, meters, >= 0.
    """

    landing_precision_m: float = Field(default=0.0, ge=0.0)
    operating_range_m: float = Field(default=0.0, ge=0.0)


# --- Site catalog ----------------------------------------------------------------------------


class Origin(StrEnum):
    """Program a catalog site comes from; used for filtering in the UI and by the AI."""

    APOLLO = "apollo"
    LUNA = "luna"
    SURVEYOR = "surveyor"
    CHANGE = "change"
    CHANDRAYAAN = "chandrayaan"
    SLIM = "slim"
    CLPS = "clps"
    ARTEMIS = "artemis"
    OTHER = "other"
    USER = "user"


class Site(_Contract):
    """A named landing site in the catalog (historical, planned, candidate or user-defined).

    Attributes:
        id: Stable slug, lowercase letters, digits and dashes (e.g. "apollo-11").
        name: Display name.
        location: Nominal landing point.
        origin: Program family, for filtering.
        status: "landed", "planned", "candidate" or "custom".
        mission: Mission name, if any (e.g. "Apollo 11").
        agency: Agency or company (e.g. "NASA", "CNSA", "ISRO", "JAXA").
        landing_date_utc: Actual or planned landing time, if known.
        landing_ellipse_m: Published landing ellipse semi-major axis, meters, if known.
        description: One or two sentences for the UI and the AI retrieval.
        sources: Citations (URL or reference) for location and facts; required unless a user site.
    """

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1)
    location: GeoPoint
    origin: Origin
    status: Literal["landed", "planned", "candidate", "custom"]
    mission: str | None = None
    agency: str | None = None
    landing_date_utc: AwareDatetime | None = None
    landing_ellipse_m: float | None = Field(default=None, gt=0.0)
    description: str = ""
    sources: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _sources_required(self) -> Self:
        """Require at least one source for every non-user site."""
        if self.origin is not Origin.USER and not self.sources:
            raise ValueError(f"site {self.id!r} needs at least one source")
        return self


# --- Module outputs --------------------------------------------------------------------------


class EphemerisSeries(_Contract):
    """Topocentric Sun and Earth directions seen from a lunar site (geometric, no terrain).

    Produced by the ephemeris module. All lists are aligned with ``times_utc``.

    Attributes:
        location: Observer site.
        times_utc: Sample times.
        sun_azimuth_deg: Sun center azimuth, degrees, [0, 360).
        sun_elevation_deg: Sun center elevation above the local horizontal, degrees.
        earth_azimuth_deg: Earth center azimuth, degrees, [0, 360).
        earth_elevation_deg: Earth center elevation above the local horizontal, degrees.
        source: Provenance, e.g. "JPL Horizons API" or the kernel set used.
    """

    location: GeoPoint
    times_utc: list[AwareDatetime]
    sun_azimuth_deg: list[float]
    sun_elevation_deg: list[float]
    earth_azimuth_deg: list[float]
    earth_elevation_deg: list[float]
    source: str

    @model_validator(mode="after")
    def _aligned(self) -> Self:
        """Require all series to have the same length as ``times_utc``."""
        _check_same_length(
            self,
            "times_utc",
            "sun_azimuth_deg",
            "sun_elevation_deg",
            "earth_azimuth_deg",
            "earth_elevation_deg",
        )
        return self


class HorizonMask(_Contract):
    """Elevation of the terrain horizon around a site, as a function of azimuth.

    Produced by the terrain module. A body is above the real horizon at azimuth ``a`` when its
    elevation exceeds the mask interpolated at ``a``.

    Attributes:
        location: Observer site.
        azimuth_deg: Strictly increasing azimuths in [0, 360), degrees.
        horizon_elevation_deg: Terrain horizon elevation at each azimuth, degrees (negative where
            the terrain falls away below the local horizontal).
        dem_source: DEM product used (name and resolution).
        dem_resolution_m: DEM pixel size, meters.
        max_distance_m: Farthest terrain distance considered when casting rays, meters.
    """

    location: GeoPoint
    azimuth_deg: list[float]
    horizon_elevation_deg: list[float]
    dem_source: str
    dem_resolution_m: float = Field(gt=0.0)
    max_distance_m: float = Field(gt=0.0)

    @model_validator(mode="after")
    def _aligned(self) -> Self:
        """Require one elevation per azimuth."""
        _check_same_length(self, "azimuth_deg", "horizon_elevation_deg")
        return self


class TerrainStats(_Contract):
    """Terrain statistics over a disk around a site.

    Attributes:
        location: Disk center.
        radius_m: Disk radius, meters (0 means the single center pixel).
        elevation_m: Center height above the 1737.4 km reference sphere, meters.
        slope_mean_deg: Mean slope over the disk, degrees.
        slope_max_deg: Maximum slope over the disk, degrees.
        dem_source: DEM product used.
        dem_resolution_m: DEM pixel size, meters.
    """

    location: GeoPoint
    radius_m: float = Field(ge=0.0)
    elevation_m: float
    slope_mean_deg: float = Field(ge=0.0, le=90.0)
    slope_max_deg: float = Field(ge=0.0, le=90.0)
    dem_source: str
    dem_resolution_m: float = Field(gt=0.0)


class VisibilityMetrics(_Contract):
    """Power and communication metrics of a site over a time window.

    "Visible" means the body's center is above the terrain horizon mask. Durations are measured on
    the sampled series: a run of n consecutive samples in the same state lasts n * step, so the
    resolution is the window step. A longest run is *truncated* when at least one run of that
    length starts at the first sample or ends at the last one: the true duration may be longer.
    An event time (sunset, sunrise, Earthset, Earthrise) is the time of the first sample in the
    new state after ``TimeWindow.start_utc``, or None when the
    transition does not happen inside the window.

    Attributes:
        illumination_fraction: Fraction of samples with the Sun visible, [0, 1].
        sun_elevation_max_deg: Maximum geometric Sun elevation in the window, degrees.
        sun_elevation_mean_visible_deg: Mean Sun elevation over visible samples; None if none.
        longest_light_h: Longest continuous Sun-visible period, hours.
        longest_light_truncated: The longest light period touches the window edge (lower bound).
        longest_dark_h: Longest continuous Sun-hidden period, hours.
        longest_dark_truncated: The longest dark period touches the window edge (lower bound).
        earth_visibility_fraction: Fraction of samples with the Earth visible, [0, 1].
        earth_elevation_mean_visible_deg: Mean Earth elevation over visible samples; None if none.
        longest_earth_visible_h: Longest continuous Earth-visible period, hours.
        longest_earth_visible_truncated: The longest contact touches the window edge.
        longest_earth_hidden_h: Longest continuous Earth-hidden period, hours.
        longest_earth_hidden_truncated: The longest outage touches the window edge.
        sun_and_earth_visible_fraction: Fraction of samples with Sun and Earth both visible
            (power and direct-to-Earth link at the same time), [0, 1].
        sun_visible_at_start: Sun visible at the window start.
        earth_visible_at_start: Earth visible at the window start.
        next_sunset_utc: First Sun visible-to-hidden transition.
        next_sunrise_utc: First Sun hidden-to-visible transition.
        next_earthset_utc: First Earth visible-to-hidden transition.
        next_earthrise_utc: First Earth hidden-to-visible transition.
    """

    illumination_fraction: float = Field(ge=0.0, le=1.0)
    sun_elevation_max_deg: float
    sun_elevation_mean_visible_deg: float | None
    longest_light_h: float = Field(ge=0.0)
    longest_light_truncated: bool
    longest_dark_h: float = Field(ge=0.0)
    longest_dark_truncated: bool
    earth_visibility_fraction: float = Field(ge=0.0, le=1.0)
    earth_elevation_mean_visible_deg: float | None
    longest_earth_visible_h: float = Field(ge=0.0)
    longest_earth_visible_truncated: bool
    longest_earth_hidden_h: float = Field(ge=0.0)
    longest_earth_hidden_truncated: bool
    sun_and_earth_visible_fraction: float = Field(ge=0.0, le=1.0)
    sun_visible_at_start: bool
    earth_visible_at_start: bool
    next_sunset_utc: AwareDatetime | None
    next_sunrise_utc: AwareDatetime | None
    next_earthset_utc: AwareDatetime | None
    next_earthrise_utc: AwareDatetime | None


class Evaluation(_Contract):
    """Full evaluation of one site over one time window: series, horizon, terrain and metrics.

    Produced by the evaluation module; the main payload of the API and the input of mission
    analysis, the AI ranking and the UI charts. Series lists are aligned with ``times_utc``.

    Attributes:
        site_id: Catalog id, or None for an ad-hoc coordinate.
        location: Evaluated point.
        window: Time window evaluated.
        area: Operations area used for the terrain statistics.
        times_utc: Sample times.
        sun_azimuth_deg: Sun azimuth per sample, degrees.
        sun_elevation_deg: Geometric Sun elevation per sample, degrees.
        sun_horizon_elevation_deg: Terrain horizon elevation at the Sun's azimuth per sample,
            degrees: the exact threshold the engine compared ``sun_elevation_deg`` with.
        sun_visible: Sun center above the terrain horizon per sample.
        earth_azimuth_deg: Earth azimuth per sample, degrees.
        earth_elevation_deg: Geometric Earth elevation per sample, degrees.
        earth_horizon_elevation_deg: Terrain horizon elevation at the Earth's azimuth per
            sample, degrees.
        earth_visible: Earth center above the terrain horizon per sample.
        horizon: Horizon mask used.
        terrain: Terrain statistics over the operations area.
        metrics: Summary metrics.
    """

    site_id: str | None
    location: GeoPoint
    window: TimeWindow
    area: OperationsArea
    times_utc: list[AwareDatetime]
    sun_azimuth_deg: list[float]
    sun_elevation_deg: list[float]
    sun_horizon_elevation_deg: list[float]
    sun_visible: list[bool]
    earth_azimuth_deg: list[float]
    earth_elevation_deg: list[float]
    earth_horizon_elevation_deg: list[float]
    earth_visible: list[bool]
    horizon: HorizonMask
    terrain: TerrainStats
    metrics: VisibilityMetrics

    @model_validator(mode="after")
    def _aligned(self) -> Self:
        """Require all series to have the same length as ``times_utc``."""
        _check_same_length(
            self,
            "times_utc",
            "sun_azimuth_deg",
            "sun_elevation_deg",
            "sun_horizon_elevation_deg",
            "sun_visible",
            "earth_azimuth_deg",
            "earth_elevation_deg",
            "earth_horizon_elevation_deg",
            "earth_visible",
        )
        return self


# --- AI and ranking --------------------------------------------------------------------------


class MissionRequirements(_Contract):
    """Mission constraints shown as editable parameters in the GUI; produced by the AI or the user.

    Every constraint is optional: None means "not constrained".

    Attributes:
        window: Time window of interest (e.g. landing date plus surface mission duration).
        area: Landing precision and operating range.
        min_illumination_fraction: Minimum fraction of time in sunlight, [0, 1].
        min_continuous_light_h: Minimum longest continuous sunlit period, hours.
        min_sun_elevation_deg: Minimum mean Sun elevation while visible, degrees.
        min_earth_visibility_fraction: Minimum fraction of time with Earth visible, [0, 1].
        min_continuous_earth_visibility_h: Minimum longest continuous Earth-visible period, hours.
        min_sun_and_earth_visible_fraction: Minimum fraction of time with Sun and Earth both
            visible, [0, 1].
        max_slope_deg: Maximum slope allowed over the operations area, degrees.
        latitude_min_deg: Southern latitude bound, degrees.
        latitude_max_deg: Northern latitude bound, degrees.
        origins: Restrict the search to these catalog programs.
        rationale: Short justification per field name, written by the AI (field name -> sentence).
        source_request: The natural-language request this was derived from, if any.
    """

    window: TimeWindow | None = None
    area: OperationsArea | None = None
    min_illumination_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    min_continuous_light_h: float | None = Field(default=None, ge=0.0)
    min_sun_elevation_deg: float | None = None
    min_earth_visibility_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    min_continuous_earth_visibility_h: float | None = Field(default=None, ge=0.0)
    min_sun_and_earth_visible_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    max_slope_deg: float | None = Field(default=None, ge=0.0, le=90.0)
    latitude_min_deg: float | None = Field(default=None, ge=-90.0, le=90.0)
    latitude_max_deg: float | None = Field(default=None, ge=-90.0, le=90.0)
    origins: list[Origin] | None = None
    rationale: dict[str, str] = Field(default_factory=dict)
    source_request: str | None = None


class SiteScore(_Contract):
    """One site's result against a set of mission requirements.

    Attributes:
        site_id: Catalog id.
        rank: 1-based position in the ranking.
        score: Aggregate score in [0, 1], higher is better (method documented by the AI module).
        constraints_met: Requirement field name -> whether this site satisfies it.
        all_constraints_met: True when every set constraint is satisfied.
        metrics: The computed metrics the score is based on.
        slope_max_deg: Maximum slope over the operations area, degrees.
        rationale: Short explanation for the user, citing the computed numbers only.
    """

    site_id: str
    rank: int = Field(ge=1)
    score: float = Field(ge=0.0, le=1.0)
    constraints_met: dict[str, bool]
    all_constraints_met: bool
    metrics: VisibilityMetrics
    slope_max_deg: float = Field(ge=0.0, le=90.0)
    rationale: str | None = None


class SiteRanking(_Contract):
    """Sites ranked against mission requirements.

    Attributes:
        requirements: The requirements used.
        results: Ranked results, best first.
    """

    requirements: MissionRequirements
    results: list[SiteScore]


class AiAnswer(_Contract):
    """Response of the AI assistant to a natural-language request.

    Attributes:
        requirements: Parameters extracted from the request (shown, editable, in the GUI).
        ranking: Catalog sites ranked by the deterministic engine against those parameters.
        message: Short answer for the user; every number in it comes from ``ranking``.
    """

    requirements: MissionRequirements
    ranking: SiteRanking
    message: str


# --- Mission analysis ------------------------------------------------------------------------


class DateShiftResult(_Contract):
    """Metrics of a site when the whole time window is shifted by ``shift_days``.

    Attributes:
        shift_days: Shift applied to the nominal window, days (positive = later).
        metrics: Metrics over the shifted window.
    """

    shift_days: float
    metrics: VisibilityMetrics


class DispersionSample(_Contract):
    """Metrics at one sampled point of the operations area.

    Attributes:
        location: Sampled point.
        offset_m: Distance from the nominal site, meters.
        metrics: Metrics at that point over the nominal window.
        slope_max_deg: Local maximum slope, degrees.
    """

    location: GeoPoint
    offset_m: float = Field(ge=0.0)
    metrics: VisibilityMetrics
    slope_max_deg: float = Field(ge=0.0, le=90.0)


class RobustnessReport(_Contract):
    """Mission analysis of a site: sensitivity to launch slips and landing dispersion.

    Attributes:
        site_id: Catalog id, or None for an ad-hoc coordinate.
        nominal: Metrics over the nominal window at the nominal point.
        date_shifts: One entry per evaluated shift.
        dispersion: One entry per sampled point of the operations area.
        summary: Short plain-language conclusion; numbers only from the fields above.
    """

    site_id: str | None
    nominal: VisibilityMetrics
    date_shifts: list[DateShiftResult]
    dispersion: list[DispersionSample]
    summary: str | None = None


# --- Globe view -------------------------------------------------------------------------------


class SkyState(_Contract):
    """Where the Sun and the Earth are overhead on the Moon at one instant (lights the 3D globe).

    Attributes:
        time_utc: The instant.
        subsolar: Point where the Sun is at the zenith (``height_m`` unset).
        sub_earth: Point where the Earth is at the zenith (``height_m`` unset).
        source: Provenance of the underlying ephemeris.
    """

    time_utc: AwareDatetime
    subsolar: GeoPoint
    sub_earth: GeoPoint
    source: str
