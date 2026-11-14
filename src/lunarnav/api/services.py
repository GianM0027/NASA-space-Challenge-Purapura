# ABOUTME: API service ports (ranking, AI) and interim implementations backed by data/examples
# ABOUTME: Owner: Gian; main.py swaps each example service for the real module (spec IF-2)

"""Service ports used by the API, plus implementations backed by ``data/examples/``.

The example-backed classes return the synthetic contract payloads so the frontend can be built
before the engine exists (spec IF-2). ``lunarnav.api.main.build_services`` swaps each of them for
the real module as soon as it is merged; they are never used once a real implementation exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pydantic import TypeAdapter

from lunarnav.contracts import (
    AiAnswer,
    Evaluation,
    Evaluator,
    GeoPoint,
    MissionAnalyzer,
    MissionRequirements,
    OperationsArea,
    RobustnessReport,
    Site,
    SiteCatalog,
    SiteRanking,
    TimeWindow,
)

EXAMPLES_DIR = Path(__file__).resolve().parents[3] / "data" / "examples"


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


class ExampleEvaluator:
    """Returns the example evaluation, relabelled with the requested point and site id."""

    def __init__(self) -> None:
        """Load the example evaluation."""
        self._example = Evaluation.model_validate_json(_read("evaluation.json"))

    def evaluate(
        self,
        location: GeoPoint,
        window: TimeWindow,
        area: OperationsArea,
        site_id: str | None = None,
    ) -> Evaluation:
        """Return the example evaluation with ``location``, ``area`` and ``site_id`` replaced."""
        return self._example.model_copy(
            update={"location": location, "area": area, "site_id": site_id}
        )


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
