# ABOUTME: FastAPI app and composition root: builds the services, exposes the REST API (IF-4)
# ABOUTME: Owner: Gian. Run: uv run uvicorn lunarnav.api.main:app --reload --port 8000

"""LunarNav REST API.

Concrete module classes are chosen in ``lunarnav.api.wiring`` (real module when its factory
exists, placeholder otherwise); ``GET /api/modules`` reports which is which.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime

from lunarnav.api.requests import (
    CommentAnalysisRequest,
    CompareRequest,
    EvaluateRequest,
    ExplainRequest,
    MissionAnalysisRequest,
    TradeoffRequest,
    UpdateSiteRequest,
)
from lunarnav.api.services import Services
from lunarnav.api.sky import sky_state
from lunarnav.api.wiring import ModuleStatus, build_services
from lunarnav.contracts import (
    AiAnswer,
    AiRequest,
    Evaluation,
    GeoPoint,
    MissionRequirements,
    ReadOnlySiteError,
    RobustnessReport,
    Site,
    SiteRanking,
    SkyState,
    TradeoffResult,
    UnknownSiteError,
)

logger = logging.getLogger(__name__)


def build_app(services: Services | None = None, status: ModuleStatus | None = None) -> FastAPI:
    """Create the FastAPI app.

    Args:
        services: Services to use; built by ``wiring.build_services`` when None.
        status: Per-service origin reported by ``GET /api/modules``; ignored unless
            ``services`` is given.

    Returns:
        The configured application.
    """
    if services is None:
        svc, modules = build_services()
    else:
        svc, modules = services, status or {}
    app = FastAPI(title="LunarNav API", version="0.1.0")

    @app.exception_handler(ValueError)
    def invalid_input(_: Request, error: ValueError) -> JSONResponse:
        """Map a module's rejection of its input to HTTP 422."""
        return JSONResponse(status_code=422, content={"detail": str(error)})

    @app.exception_handler(Exception)
    def module_failure(_: Request, error: Exception) -> JSONResponse:
        """Map any other module failure (Horizons, LLM, data files) to HTTP 502 for the UI."""
        logger.exception("module failure")
        detail = f"{type(error).__name__}: {error}"
        return JSONResponse(status_code=502, content={"detail": detail})

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

    @app.get("/api/modules")
    def module_status() -> ModuleStatus:
        """Report, per service, whether it is "real", "example" or "error: ..."."""
        return modules

    @app.get("/api/sky")
    def sky(time_utc: AwareDatetime) -> SkyState:
        """Subsolar and sub-Earth points at an instant (lights the globe)."""
        return sky_state(svc.ephemeris, time_utc)

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

    def require_editable_catalog(method: str) -> None:
        """Answer 501 while the wired catalog lacks a ``SiteCatalog`` method added later."""
        if not callable(getattr(svc.catalog, method, None)):
            name = type(svc.catalog).__name__
            raise HTTPException(501, f"{name} does not implement {method} yet")

    @app.delete("/api/sites/{site_id}", status_code=204)
    def remove_site(site_id: str) -> Response:
        """Delete a user site; 404 if unknown, 403 if curated."""
        require_editable_catalog("remove_user_site")
        try:
            svc.catalog.remove_user_site(site_id)
        except UnknownSiteError as error:
            raise HTTPException(404, f"unknown site id {site_id!r}") from error
        except ReadOnlySiteError as error:
            raise HTTPException(403, str(error)) from error
        return Response(status_code=204)

    @app.patch("/api/sites/{site_id}")
    def update_site(site_id: str, request: UpdateSiteRequest) -> Site:
        """Edit a user site's name and/or description (id unchanged).

        404 if unknown, 403 if curated, 422 if the body is empty or the name blank.
        """
        require_editable_catalog("update_user_site")
        try:
            return svc.catalog.update_user_site(
                site_id, name=request.name, description=request.description
            )
        except UnknownSiteError as error:
            raise HTTPException(404, f"unknown site id {site_id!r}") from error
        except ReadOnlySiteError as error:
            raise HTTPException(403, str(error)) from error

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
    def ask(request: AiRequest) -> AiAnswer:
        """Turn one chat turn into updated requirements and, when possible, a ranking."""
        return svc.assistant.ask(request)

    @app.post("/api/ai/explain")
    def explain(request: ExplainRequest) -> SiteRanking:
        """Add a short AI rationale to every ranked site (numbers checked against the ranking)."""
        return svc.assistant.explain(request.ranking, request.language_hint)

    def tradeoff(request: TradeoffRequest) -> tuple[TradeoffResult, list[Evaluation]]:
        """Evaluate the scenarios and run the trade-off on them."""
        evaluations = [evaluate(scenario) for scenario in request.scenarios]
        return svc.tradeoff.analyze(evaluations, request.settings), evaluations

    @app.post("/api/tradeoff")
    def tradeoff_result(request: TradeoffRequest) -> TradeoffResult:
        """AHP trade-off of 2 to 4 scenarios (spec section 4.8)."""
        return tradeoff(request)[0]

    @app.post("/api/tradeoff/export")
    def tradeoff_export(request: TradeoffRequest) -> Response:
        """The same trade-off as a live Excel workbook (spec TO-4); 501 without the module."""
        export = getattr(svc.tradeoff, "export_xlsx", None)
        if not callable(export):
            raise HTTPException(501, f"{type(svc.tradeoff).__name__} cannot export a workbook yet")
        result, evaluations = tradeoff(request)
        content = export(result, evaluations)
        return Response(
            content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="lunarnav-tradeoff.xlsx"'},
        )

    @app.post("/api/ai/comment-analysis")
    def comment_analysis(request: CommentAnalysisRequest) -> RobustnessReport:
        """Add a short AI comment to a mission-analysis report (numbers checked)."""
        return svc.assistant.comment_analysis(
            request.report, request.site_name, request.language_hint
        )

    @app.post("/api/mission-analysis")
    def mission_analysis(request: MissionAnalysisRequest) -> RobustnessReport:
        """Robustness of a scenario to date shifts and landing dispersion."""
        location, site_id = resolve(request)
        return svc.analyzer.analyze(
            location, request.window, request.area, request.shifts_days, site_id=site_id
        )

    return app


app = build_app()
