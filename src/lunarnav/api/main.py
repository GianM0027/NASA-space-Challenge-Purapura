# ABOUTME: FastAPI app and composition root: builds the services, exposes the REST API (IF-4)
# ABOUTME: Owner: Gian. Run: uv run uvicorn lunarnav.api.main:app --reload --port 8000

"""LunarNav REST API.

``build_services`` is the single place where concrete module classes are chosen and wired;
swap an example-backed service for the real module there when it is merged.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from lunarnav.api.requests import (
    AskRequest,
    CompareRequest,
    EvaluateRequest,
    MissionAnalysisRequest,
)
from lunarnav.api.services import (
    ExampleAnalyzer,
    ExampleAssistant,
    ExampleCatalog,
    ExampleEvaluator,
    ExampleRanker,
    Services,
)
from lunarnav.contracts import (
    AiAnswer,
    Evaluation,
    GeoPoint,
    MissionRequirements,
    RobustnessReport,
    Site,
    SiteRanking,
)


def build_services() -> Services:
    """Build the concrete services (composition root).

    Returns:
        The services the API uses; example-backed until each real module is merged.
    """
    return Services(
        catalog=ExampleCatalog(),
        evaluator=ExampleEvaluator(),
        analyzer=ExampleAnalyzer(),
        ranker=ExampleRanker(),
        assistant=ExampleAssistant(),
    )


def build_app(services: Services | None = None) -> FastAPI:
    """Create the FastAPI app.

    Args:
        services: Services to use; built by ``build_services`` when None.

    Returns:
        The configured application.
    """
    svc = services or build_services()
    app = FastAPI(title="LunarNav API", version="0.1.0")

    def resolve(request: EvaluateRequest) -> tuple[GeoPoint, str | None]:
        """Return the point to evaluate and its site id; 404 for an unknown site."""
        if request.site_id is None:
            assert request.location is not None  # guaranteed by EvaluateRequest validation
            return request.location, None
        try:
            return svc.catalog.get_site(request.site_id).location, request.site_id
        except KeyError as error:
            raise HTTPException(404, f"unknown site id {request.site_id!r}") from error

    def evaluate(request: EvaluateRequest) -> Evaluation:
        """Evaluate one resolved scenario."""
        location, site_id = resolve(request)
        return svc.evaluator.evaluate(location, request.window, request.area, site_id=site_id)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        """Liveness check."""
        return {"status": "ok"}

    @app.get("/api/sites")
    def list_sites() -> list[Site]:
        """List all catalog and user sites."""
        return svc.catalog.list_sites()

    @app.post("/api/sites")
    def add_site(site: Site) -> Site:
        """Add a user site; 409 if the id exists."""
        try:
            return svc.catalog.add_user_site(site)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @app.post("/api/evaluate")
    def evaluate_one(request: EvaluateRequest) -> Evaluation:
        """Evaluate one site or point over a window."""
        return evaluate(request)

    @app.post("/api/compare")
    def compare(request: CompareRequest) -> list[Evaluation]:
        """Evaluate 2 to 4 scenarios side by side."""
        return [evaluate(scenario) for scenario in request.scenarios]

    @app.post("/api/rank")
    def rank(requirements: MissionRequirements) -> SiteRanking:
        """Rank catalog sites against explicit requirements (no LLM)."""
        return svc.ranker.rank(requirements)

    @app.post("/api/ai/ask")
    def ask(request: AskRequest) -> AiAnswer:
        """Turn a natural-language request into requirements and a ranking."""
        return svc.assistant.ask(request.text)

    @app.post("/api/mission-analysis")
    def mission_analysis(request: MissionAnalysisRequest) -> RobustnessReport:
        """Robustness of a scenario to date shifts and landing dispersion."""
        location, site_id = resolve(request)
        return svc.analyzer.analyze(
            location, request.window, request.area, request.shifts_days, site_id=site_id
        )

    return app


app = build_app()
