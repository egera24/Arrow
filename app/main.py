import asyncio
import time

from fastapi import Body, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import Settings, get_settings
from app.debug_log import agent_log
from app.model_selection import MODEL_SELECTION_HINT, GeminiModel, SUPPORTED_GEMINI_MODELS, resolve_model
from app.models import (
    TICKET_EXAMPLE,
    BatchAnalyzeJsonRequest,
    BatchAnalyzeResponse,
    ClassifyResponse,
    HealthResponse,
    ModelsResponse,
    TicketInput,
)
from app.providers.base import LLMProvider
from app.providers.errors import ProviderUnavailableError
from app.providers.factory import get_provider
from app.services.batch_analyzer import analyze_batch
from app.services.classifier import classify_ticket
from app.state import batch_result_to_csv, get_last_batch_result, parse_tickets_csv, set_last_batch_result

app = FastAPI(
    title="Support Ticket Intelligence API",
    description=(
        "Classifies support tickets and generates batch trend insights using AI. "
        "Built as a demo for data pipeline and analytics automation workflows."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Duration-Ms"],
)


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()
        origin = request.headers.get("origin", "")
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        # #region agent log
        agent_log(
            hypothesis_id="H5",
            location="app/main.py:RequestLogMiddleware",
            message="request completed",
            data={
                "path": request.url.path,
                "method": request.method,
                "origin": origin if origin else "(none)",
                "status_code": response.status_code,
                "elapsed_ms": elapsed_ms,
            },
            run_id="post-fix",
        )
        # #endregion
        response.headers["X-Request-Duration-Ms"] = str(elapsed_ms)
        return response


app.add_middleware(RequestLogMiddleware)

MODEL_QUERY = Query(
    default=None,
    description="Optional Gemini model override. Leave empty to use AI_MODEL from .env.",
)


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


def _resolve_model_or_400(requested: str | GeminiModel | None, settings: Settings) -> str:
    try:
        return resolve_model(requested, settings.ai_model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _provider_for_request(settings: Settings, model: str) -> LLMProvider:
    return get_provider(settings, model=model)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    detail = exc.errors()
    for error in detail:
        if error.get("loc") == ("body", "created_at") and error.get("input") == "string":
            error["hint"] = (
                'Swagger often pre-fills "string" for optional fields. '
                "Remove created_at or use an ISO datetime like 2026-05-28T09:15:00."
            )
        if error.get("loc") == ("body", "demo_mode"):
            error["hint"] = "demo_mode is a response field only. Set DEMO_MODE in .env, not in the request body."
        if error.get("loc") == ("query", "model") and error.get("input") == "string":
            error["hint"] = "Clear the model field or pick a value from the dropdown. Do not leave the placeholder 'string'."
    return JSONResponse(status_code=422, content={"detail": detail})


@app.exception_handler(ProviderUnavailableError)
async def provider_unavailable_handler(_request: object, exc: ProviderUnavailableError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.get("/models", response_model=ModelsResponse)
async def list_models() -> ModelsResponse:
    settings = get_settings()
    return ModelsResponse(
        default_model=settings.ai_model,
        supported_models=list(SUPPORTED_GEMINI_MODELS),
        hint=MODEL_SELECTION_HINT,
    )


PING_TIMEOUT_SECONDS = 20


@app.get("/health/live", include_in_schema=False)
async def health_live() -> dict[str, str]:
    """Fast liveness probe for Render (no external API calls)."""
    # #region agent log
    agent_log(
        hypothesis_id="H4",
        location="app/main.py:health_live",
        message="liveness probe",
        data={"path": "/health/live"},
    )
    # #endregion
    return {"status": "ok"}


@app.get("/health", response_model=HealthResponse)
async def health(
    request: Request,
    model: GeminiModel | None = MODEL_QUERY,
) -> HealthResponse:
    started = time.perf_counter()
    # #region agent log
    agent_log(
        hypothesis_id="H1",
        location="app/main.py:health:entry",
        message="health check started",
        data={
            "model": model.value if isinstance(model, GeminiModel) else model,
            "client_host": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent", "")[:80],
        },
    )
    # #endregion
    settings = get_settings()
    effective_model = _resolve_model_or_400(model, settings)
    provider = _provider_for_request(settings, effective_model)
    api_key_configured = bool(settings.ai_api_key) and settings.ai_api_key != "your_gemini_api_key_here"

    reachable: bool | None = None
    message: str | None = None
    status: str = "ok"

    if settings.demo_mode or not api_key_configured:
        message = "Running in demo mode or without API key."
    else:
        try:
            reachable, ping_detail = await asyncio.wait_for(
                provider.ping(),
                timeout=PING_TIMEOUT_SECONDS,
            )
            if not reachable:
                status = "degraded"
                message = ping_detail or "API key is configured but provider ping failed."
        except asyncio.TimeoutError:
            status = "degraded"
            reachable = False
            message = f"Provider ping timed out after {PING_TIMEOUT_SECONDS}s."
            # #region agent log
            agent_log(
                hypothesis_id="H3",
                location="app/main.py:health:ping_timeout",
                message="gemini ping timed out",
                data={"model": effective_model, "timeout_seconds": PING_TIMEOUT_SECONDS},
            )
            # #endregion
        except Exception as exc:
            status = "degraded"
            reachable = False
            message = f"Provider ping failed: {exc}"
            # #region agent log
            agent_log(
                hypothesis_id="H2",
                location="app/main.py:health:ping_error",
                message="gemini ping raised",
                data={"model": effective_model, "error_type": type(exc).__name__},
            )
            # #endregion

    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    # #region agent log
    agent_log(
        hypothesis_id="H1",
        location="app/main.py:health:exit",
        message="health check finished",
        data={
            "status": status,
            "model": effective_model,
            "provider_reachable": reachable,
            "elapsed_ms": elapsed_ms,
        },
    )
    # #endregion

    return HealthResponse(
        status=status,
        provider=provider.name,
        api_key_configured=api_key_configured,
        demo_mode=settings.demo_mode or provider.name == "mock",
        model=effective_model,
        provider_reachable=reachable,
        message=message,
    )


@app.post("/tickets/classify", response_model=ClassifyResponse)
async def tickets_classify(
    ticket: TicketInput = Body(
        openapi_examples={
            "login_issue": {
                "summary": "Login failure ticket",
                "value": TICKET_EXAMPLE,
            }
        }
    ),
    model: GeminiModel | None = MODEL_QUERY,
) -> ClassifyResponse:
    settings = get_settings()
    effective_model = _resolve_model_or_400(model, settings)
    provider = _provider_for_request(settings, effective_model)
    classification, provider_used = await classify_ticket(provider, ticket)
    return ClassifyResponse(
        ticket_id=ticket.ticket_id,
        classification=classification,
        provider=provider_used,
        model=effective_model,
        demo_mode=provider_used == "mock",
    )


@app.post("/tickets/analyze-batch", response_model=BatchAnalyzeResponse)
async def tickets_analyze_batch_json(
    payload: BatchAnalyzeJsonRequest = Body(
        openapi_examples={
            "two_tickets": {
                "summary": "Small batch example",
                "value": {
                    "tickets": [
                        TICKET_EXAMPLE,
                        {
                            "ticket_id": "TKT-1006",
                            "subject": "Duplicate invoice for April",
                            "description": "Customer billed twice for subscription renewal.",
                        },
                    ]
                },
            }
        }
    ),
    model: GeminiModel | None = MODEL_QUERY,
) -> BatchAnalyzeResponse:
    if not payload.tickets:
        raise HTTPException(status_code=400, detail="At least one ticket is required.")
    settings = get_settings()
    effective_model = _resolve_model_or_400(model, settings)
    provider = _provider_for_request(settings, effective_model)
    result = await analyze_batch(provider, payload.tickets, limit=settings.batch_size_limit, model=effective_model)
    set_last_batch_result(result)
    return result


@app.post("/tickets/analyze-batch/upload", response_model=BatchAnalyzeResponse)
async def tickets_analyze_batch_upload(
    file: UploadFile = File(...),
    model: GeminiModel | None = MODEL_QUERY,
) -> BatchAnalyzeResponse:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a CSV file with columns: ticket_id, subject, description, created_at")
    content = await file.read()
    try:
        tickets = parse_tickets_csv(content)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid CSV format: {exc}") from exc
    if not tickets:
        raise HTTPException(status_code=400, detail="CSV contains no ticket rows.")
    settings = get_settings()
    effective_model = _resolve_model_or_400(model, settings)
    provider = _provider_for_request(settings, effective_model)
    result = await analyze_batch(provider, tickets, limit=settings.batch_size_limit, model=effective_model)
    set_last_batch_result(result)
    return result


@app.get("/tickets/export")
async def tickets_export() -> PlainTextResponse:
    result = get_last_batch_result()
    if result is None:
        raise HTTPException(status_code=404, detail="No batch results available. Run analyze-batch first.")
    csv_content = batch_result_to_csv(result)
    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ticket_classifications.csv"},
    )


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    for path_item in openapi_schema.get("paths", {}).values():
        for operation in path_item.values():
            if isinstance(operation, dict):
                operation.get("responses", {}).pop("422", None)
    openapi_schema["servers"] = [{"url": "/"}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
