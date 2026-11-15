# ABOUTME: Request bodies of the REST API (spec IF-4) that are not contract models themselves
# ABOUTME: Owner: Gian; responses are always contract models from lunarnav.contracts

"""API request models: they reference contract types but exist only at the HTTP boundary."""

from __future__ import annotations

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from lunarnav.contracts import GeoPoint, OperationsArea, SiteRanking, TimeWindow


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


class MissionAnalysisRequest(EvaluateRequest):
    """Evaluate a scenario's robustness to date shifts and landing dispersion.

    Attributes:
        shifts_days: Window shifts to evaluate, days (positive = later).
    """

    shifts_days: list[float] = Field(default_factory=lambda: [1.0, 3.0, 7.0, 14.0])


class ExplainRequest(BaseModel):
    """Ask the AI for a short rationale per ranked site.

    Attributes:
        ranking: A ranking returned by ``/api/rank`` or ``/api/ai/ask``.
        language_hint: The user's latest message, so the text matches their language.
    """

    model_config = ConfigDict(extra="forbid")

    ranking: SiteRanking
    language_hint: str = Field(default="", max_length=4000)


class RenameSiteRequest(BaseModel):
    """Rename a user site; the id never changes.

    Attributes:
        name: New display name, stripped of surrounding whitespace, at least one character.
    """

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
