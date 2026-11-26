# ABOUTME: FastAPI app and composition root: builds the services, exposes the REST API (IF-4)
# ABOUTME: Owner: Gian. Run: uv run uvicorn lunarnav.api.main:app --reload --port 8000

"""LunarNav REST API.

Concrete module classes are chosen in ``lunarnav.api.wiring`` (real module when its factory
exists, placeholder otherwise); ``GET /api/modules`` reports which is which.

AI routes accept the caller's own Anthropic API key in the ``X-Anthropic-Api-Key`` header
(decision D43): the key answers that request only and is never stored or logged. Without it the
server's provider answers (``LUNARNAV_LLM_PROVIDER``); with none, ``/api/ai/ask`` answers 503
and the other AI texts fall back to their deterministic versions.
"""

from __future__ import annotations

import logging
from types import ModuleType
from typing import Annotated, Any

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime

from lunarnav.accounts import AccountError, AccountStore, build_account_store
from lunarnav.api.accounts import SessionDep, build_accounts_router
from lunarnav.api.ratelimit import RateLimitMiddleware, limiter_from_env
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
    SiteCatalog,
    SiteRanking,
    SkyState,
    TradeoffResult,
    UnknownSiteError,
)

logger = logging.getLogger(__name__)

# Header carrying a user's own Anthropic API key for the AI routes (decision D43).
API_KEY_HEADER = "X-Anthropic-Api-Key"
ApiKey = Annotated[str | None, Header(alias=API_KEY_HEADER)]


def _llm_module() -> ModuleType | None:
    """Return ``lunarnav.ai.llm``, or None when the AI module is not installed."""
    try:
        from lunarnav.ai import llm
    except ImportError:
        return None
    return llm


# How many trade-off comments the API keeps for the export to reuse (oldest dropped first).
TRADEOFF_COMMENT_CACHE = 32


def build_app(
    services: Services | None = None,
    status: ModuleStatus | None = None,
    accounts: AccountStore | None = None,
) -> FastAPI:
    """Create the FastAPI app.

    Args:
        services: Services to use; built by ``wiring.build_services`` when None.
        status: Per-service origin reported by ``GET /api/modules``; ignored unless
            ``services`` is given.
        accounts: Account store; opened from the environment when None (decision D45).

    Returns:
        The configured application.
    """
    if services is None:
        svc, modules = build_services()
    else:
        svc, modules = services, status or {}
    if accounts is None:
        accounts = build_account_store()
    app = FastAPI(title="LunarNav API", version="0.1.0")
    limiter = limiter_from_env()
    if limiter is not None:  # per-client limits for the public deployment (decision D44)
        app.add_middleware(RateLimitMiddleware, limiter=limiter)

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

    llm_module = _llm_module()
    if llm_module is not None:
        # Registered per class (not in the catch-all above) so these answers are final: AI
        # failures the user can fix are not server errors and leave no traceback in the log.

        @app.exception_handler(llm_module.LlmAuthError)
        def rejected_key(_: Request, error: Exception) -> JSONResponse:
            """Anthropic rejected the caller's key: 401."""
            return JSONResponse(
                status_code=401,
                content={"detail": "The Anthropic API key was rejected: check it and try again."},
            )

        @app.exception_handler(llm_module.LlmUnavailableError)
        def no_llm(_: Request, error: Exception) -> JSONResponse:
            """No server LLM and no key in the request: 503."""
            return JSONResponse(
                status_code=503, content={"detail": "The AI assistant needs an Anthropic API key."}
            )

    # Accounts (decision D45): every route below sees the catalog of the person asking.
    app.state.accounts = accounts
    app.state.base_catalog = svc.catalog
    app.include_router(build_accounts_router(accounts))

    def ranker_for(catalog: SiteCatalog) -> Any:
        """The ranker over this person's catalog (their own sites included)."""
        with_catalog = getattr(svc.ranker, "with_catalog", None)
        return with_catalog(catalog) if callable(with_catalog) else svc.ranker

    def resolve(request: EvaluateRequest, catalog: SiteCatalog) -> tuple[GeoPoint, str | None]:
        """Return the point to evaluate and its site id; 404 for a site this person cannot see."""
        if request.site_id is None:
            assert request.location is not None  # guaranteed by EvaluateRequest validation
            return request.location, None
        try:
            return catalog.get_site(request.site_id).location, request.site_id
        except KeyError as error:
            raise HTTPException(404, f"unknown site id {request.site_id!r}") from error

    def evaluate(request: EvaluateRequest, catalog: SiteCatalog) -> Evaluation:
        """Evaluate one resolved scenario."""
        location, site_id = resolve(request, catalog)
        return svc.evaluator.evaluate(location, request.window, request.area, site_id=site_id)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        """Liveness check."""
        return {"status": "ok"}

    @app.get("/api/modules")
    def module_status() -> ModuleStatus:
        """Report, per service, whether it is "real", "example" or "error: ..."."""
        return modules

    def assistant_for(api_key: str | None, catalog: SiteCatalog) -> Any:
        """Return the assistant for this request: the caller's key and their catalog.

        Without a key the server's LLM answers. 422 for a key of impossible shape; 501 when the
        wired assistant cannot take a key.
        """
        rebind = getattr(svc.assistant, "rebind", None)
        llm_client = None
        if api_key is not None and api_key.strip():
            llm = _llm_module()
            if llm is None or not callable(rebind):
                raise HTTPException(501, "this server cannot use an Anthropic API key")
            try:
                llm_client = llm.api_client_for_key(api_key)
            except ValueError as error:
                raise HTTPException(422, str(error)) from error
        if not callable(rebind):
            return svc.assistant
        return rebind(llm=llm_client, ranker=ranker_for(catalog), catalog=catalog)

    @app.get("/api/ai/config")
    def ai_config() -> dict[str, Any]:
        """Report the server's LLM provider and whether a user key is accepted.

        ``server_llm``: "cli", "api" or "none"; "example" for the placeholder assistant.
        """
        server_llm = getattr(getattr(svc.assistant, "llm", None), "provider", None)
        return {
            "server_llm": server_llm or "example",
            "accepts_user_key": callable(getattr(svc.assistant, "rebind", None))
            and _llm_module() is not None,
            "key_header": API_KEY_HEADER,
        }

    @app.get("/api/sky")
    def sky(time_utc: AwareDatetime) -> SkyState:
        """Subsolar and sub-Earth points at an instant (lights the globe)."""
        return sky_state(svc.ephemeris, time_utc)

    @app.get("/api/sites")
    def list_sites(session: SessionDep) -> list[Site]:
        """Shared catalog sites, then the visitor's own sites."""
        return session.catalog().list_sites()

    @app.post("/api/sites")
    def add_site(site: Site, session: SessionDep, response: Response) -> Site:
        """Save a personal site (a first save starts a guest session); 409 if the id exists."""
        try:
            saved = session.catalog().add_user_site(site)
        except AccountError as error:
            raise HTTPException(409, str(error)) from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        session.write_cookie(response)
        return saved

    @app.delete("/api/sites/{site_id}", status_code=204)
    def remove_site(site_id: str, session: SessionDep) -> Response:
        """Delete a personal site; 404 if unknown, 403 if it belongs to the shared catalog."""
        try:
            session.catalog().remove_user_site(site_id)
        except UnknownSiteError as error:
            raise HTTPException(404, f"unknown site id {site_id!r}") from error
        except ReadOnlySiteError as error:
            raise HTTPException(403, str(error)) from error
        return Response(status_code=204)

    @app.patch("/api/sites/{site_id}")
    def update_site(site_id: str, request: UpdateSiteRequest, session: SessionDep) -> Site:
        """Edit a personal site's name and/or description (id unchanged).

        404 if unknown, 403 if shared, 422 if the body is empty or the name blank.
        """
        try:
            return session.catalog().update_user_site(
                site_id, name=request.name, description=request.description
            )
        except UnknownSiteError as error:
            raise HTTPException(404, f"unknown site id {site_id!r}") from error
        except ReadOnlySiteError as error:
            raise HTTPException(403, str(error)) from error

    @app.post("/api/evaluate")
    def evaluate_one(request: EvaluateRequest, session: SessionDep) -> Evaluation:
        """Evaluate one site or point over a window."""
        return evaluate(request, session.catalog())

    @app.post("/api/compare")
    def compare(request: CompareRequest, session: SessionDep) -> list[Evaluation]:
        """Evaluate 2 to 4 scenarios side by side."""
        catalog = session.catalog()
        return [evaluate(scenario, catalog) for scenario in request.scenarios]

    @app.post("/api/rank")
    def rank(requirements: MissionRequirements, session: SessionDep) -> SiteRanking:
        """Rank catalog sites (and the visitor's own) against explicit requirements (no LLM)."""
        return ranker_for(session.catalog()).rank(requirements)

    @app.post("/api/ai/ask")
    def ask(request: AiRequest, session: SessionDep, api_key: ApiKey = None) -> AiAnswer:
        """Turn one chat turn into updated requirements and, when possible, a ranking."""
        return assistant_for(api_key, session.catalog()).ask(request)

    @app.post("/api/ai/explain")
    def explain(
        request: ExplainRequest, session: SessionDep, api_key: ApiKey = None
    ) -> SiteRanking:
        """Add a short AI rationale to every ranked site (numbers checked against the ranking)."""
        return assistant_for(api_key, session.catalog()).explain(
            request.ranking, request.language_hint
        )

    # AI comments of the latest trade-off results, keyed by the result without comment: the
    # export recomputes the same deterministic result and reuses its comment, no second LLM call.
    # Only comments that exist are kept, so a result without one is asked again next time.
    tradeoff_comments: dict[str, str] = {}

    def tradeoff(
        request: TradeoffRequest, api_key: str | None, catalog: SiteCatalog
    ) -> tuple[TradeoffResult, list[Evaluation]]:
        """Evaluate the scenarios, run the trade-off and add its AI comment (spec TO-5)."""
        evaluations = [evaluate(scenario, catalog) for scenario in request.scenarios]
        result = svc.tradeoff.analyze(evaluations, request.settings)
        key = result.model_dump_json(exclude={"ai_comment"})
        comment = tradeoff_comments.get(key)
        if comment is None:
            comment = assistant_for(api_key, catalog).comment_tradeoff(result).ai_comment
            if comment is not None:
                if len(tradeoff_comments) >= TRADEOFF_COMMENT_CACHE:
                    tradeoff_comments.pop(next(iter(tradeoff_comments)))
                tradeoff_comments[key] = comment
        return result.model_copy(update={"ai_comment": comment}), evaluations

    @app.post("/api/tradeoff")
    def tradeoff_result(
        request: TradeoffRequest, session: SessionDep, api_key: ApiKey = None
    ) -> TradeoffResult:
        """AHP trade-off of 2 to 4 scenarios (spec section 4.8)."""
        return tradeoff(request, api_key, session.catalog())[0]

    @app.post("/api/tradeoff/export")
    def tradeoff_export(
        request: TradeoffRequest, session: SessionDep, api_key: ApiKey = None
    ) -> Response:
        """The same trade-off as a live Excel workbook (spec TO-4); 501 without the module."""
        export = getattr(svc.tradeoff, "export_xlsx", None)
        if not callable(export):
            raise HTTPException(501, f"{type(svc.tradeoff).__name__} cannot export a workbook yet")
        result, evaluations = tradeoff(request, api_key, session.catalog())
        content = export(result, evaluations)
        return Response(
            content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="lunarnav-tradeoff.xlsx"'},
        )

    @app.post("/api/ai/comment-analysis")
    def comment_analysis(
        request: CommentAnalysisRequest, session: SessionDep, api_key: ApiKey = None
    ) -> RobustnessReport:
        """Add a short AI comment to a mission-analysis report (numbers checked)."""
        return assistant_for(api_key, session.catalog()).comment_analysis(
            request.report, request.site_name, request.language_hint
        )

    @app.post("/api/mission-analysis")
    def mission_analysis(request: MissionAnalysisRequest, session: SessionDep) -> RobustnessReport:
        """Robustness of a scenario to date shifts and landing dispersion."""
        location, site_id = resolve(request, session.catalog())
        return svc.analyzer.analyze(
            location, request.window, request.area, request.shifts_days, site_id=site_id
        )

    return app


app = build_app()
