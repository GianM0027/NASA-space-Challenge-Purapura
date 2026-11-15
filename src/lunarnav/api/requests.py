# ABOUTME: Request bodies of the REST API (spec IF-4) that are not contract models themselves
# ABOUTME: Owner: Gian; responses are always contract models from lunarnav.contracts

"""API request models: they reference contract types but exist only at the HTTP boundary."""

from __future__ import annotations

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from lunarnav.contracts import (
    GeoPoint,
    OperationsArea,
    RobustnessReport,
    SiteRanking,
    TimeWindow,
    TradeoffSettings,
)


class EvaluateRequest(BaseModel):
    """Evaluate one scenario: a catalog site or an ad-hoc point, over a window.

    Attributes:
        site_id: Catalog id; exclusive with ``location``.
        location: Ad-hoc point; exclusive with ``site_id``.
        window: Time window to evaluate.
        area: Landing precision and operating range (defaults to a single point).
    """

    model_config = ConfigDict(extra="forbid")

    site_id: str | None = None
    location: GeoPoint | None = None
    window: TimeWindow
    area: OperationsArea = Field(default_factory=OperationsArea)

    @model_validator(mode="after")
    def _exactly_one_target(self) -> Self:
        """Require exactly one of ``site_id`` and ``location``."""
        if (self.site_id is None) == (self.location is None):
            raise ValueError("give exactly one of site_id and location")
        return self


class CompareRequest(BaseModel):
    """Evaluate 2 to 4 scenarios side by side.

    Attributes:
        scenarios: The scenarios, in display order.
    """

    model_config = ConfigDict(extra="forbid")

    scenarios: list[EvaluateRequest] = Field(min_length=2, max_length=4)


class TradeoffRequest(BaseModel):
    """Trade-off of 2 to 4 scenarios (spec section 4.8).

    Attributes:
        scenarios: The scenarios, evaluated like ``/api/evaluate``, in the order of the labels.
        settings: Labels, weights or pairwise judgments, user FoMs, excluded FoMs.
    """

    model_config = ConfigDict(extra="forbid")

    scenarios: list[EvaluateRequest] = Field(min_length=2, max_length=4)
    settings: TradeoffSettings

    @model_validator(mode="after")
    def _one_label_per_scenario(self) -> Self:
        """Reject labels that do not match the scenarios one to one.

        Raises:
            ValueError: If the label count differs from the scenario count.
        """
        if len(self.settings.labels) != len(self.scenarios):
            raise ValueError("give one label per scenario")
        return self


class MissionAnalysisRequest(EvaluateRequest):
    """Evaluate a scenario's robustness to date shifts and landing dispersion.

    Attributes:
        shifts_days: Window shifts to evaluate, days (positive = later); empty (the default)
            lets the mission-analysis module use its own default shifts.
    """

    shifts_days: list[float] = Field(default_factory=list)


class CommentAnalysisRequest(BaseModel):
    """Ask the AI for a short comment on a mission-analysis report (spec AI-6).

    Attributes:
        report: A report returned by ``/api/mission-analysis``.
        site_name: Display name of the analyzed site or point.
        language_hint: The user's latest message, so the text matches their language.
    """

    model_config = ConfigDict(extra="forbid")

    report: RobustnessReport
    site_name: str = Field(max_length=200)
    language_hint: str = Field(default="", max_length=4000)


class ExplainRequest(BaseModel):
    """Ask the AI for a short rationale per ranked site.

    Attributes:
        ranking: A ranking returned by ``/api/rank`` or ``/api/ai/ask``.
        language_hint: The user's latest message, so the text matches their language.
    """

    model_config = ConfigDict(extra="forbid")

    ranking: SiteRanking
    language_hint: str = Field(default="", max_length=4000)


SiteName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
SiteDescription = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


class UpdateSiteRequest(BaseModel):
    """Edit the name and/or description of a user site; the id never changes.

    Attributes:
        name: New display name, stripped, at least one character; None keeps the current one.
        description: New description, stripped; None keeps it, "" clears it.
    """

    model_config = ConfigDict(extra="forbid")

    name: SiteName | None = None
    description: SiteDescription | None = None

    @model_validator(mode="after")
    def _one_field(self) -> Self:
        """Reject a body that changes nothing.

        Raises:
            ValueError: If neither ``name`` nor ``description`` is given.
        """
        if self.name is None and self.description is None:
            raise ValueError("give a name, a description, or both")
        return self
