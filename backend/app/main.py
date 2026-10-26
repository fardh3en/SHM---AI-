"""
FastAPI application factory.

Registers routers, middleware, exception handlers, and lifecycle hooks.
Configures automatic DB initialization in development environments.
"""
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.v1.router import api_router
from backend.app.config import get_settings
from backend.app.core.exceptions import SHMBaseException
from backend.app.core.logging import configure_logging
from backend.app.database.session import create_db_and_tables

# ── Logging Setup ────────────────────────────────────────────────────────────
# Must occur before any other loggers are instantiated.
configure_logging()
logger = logging.getLogger(__name__)

settings = get_settings()


# ── Application Lifespan ──────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Startup and shutdown lifecycle manager.
    """
    logger.info("Initializing SHM-AI Platform backend service...")

    # Ensure essential runtime directories exist across all environments
    os.makedirs(settings.BASE_DIR / "data", exist_ok=True)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.UPLOAD_DIR / "evidence", exist_ok=True)
    os.makedirs(settings.WEIGHTS_DIR, exist_ok=True)

    # Initialize and verify database tables across all environments (including production)
    try:
        await create_db_and_tables()
    except Exception as db_exc:
        logger.critical(
            "FATAL: Database schema initialization failed at startup: %s. Terminating server before accepting requests.",
            db_exc,
            exc_info=True,
        )
        raise

    # Safe startup verification of core vision runtime environment
    try:
        from scripts.verify_vision_environment import verify_vision_environment
        vision_report = verify_vision_environment(verbose=False)
        if vision_report.get("healthy"):
            logger.info(
                "Vision runtime verified: torch=%s (device=%s), ultralytics=%s, cv2=%s, model=%s",
                vision_report["versions"].get("torch"),
                vision_report.get("device"),
                vision_report["versions"].get("ultralytics"),
                vision_report["versions"].get("cv2"),
                vision_report.get("model_file"),
            )
        else:
            logger.warning(
                "Vision runtime incomplete at startup: %s. Vision inference will fail until dependencies/weights are provisioned.",
                "; ".join(vision_report.get("errors", [])),
            )
    except Exception as v_err:
        logger.warning("Vision environment check encountered unexpected error: %s", v_err)

    yield

    logger.info("Shutting down SHM-AI Platform backend service...")


# ── App Instantiation ─────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Structural Health Monitoring & Predictive Maintenance AI Platform API",
    lifespan=lifespan,
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
)


# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_origin_regex=settings.ALLOWED_ORIGIN_REGEX,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)


# ── Exception Handlers ────────────────────────────────────────────────────────
@app.exception_handler(SHMBaseException)
async def shm_exception_handler(request: Request, exc: SHMBaseException) -> JSONResponse:
    """Map domain-specific exceptions to client-friendly JSON responses."""
    status_code = getattr(exc, "http_status", status.HTTP_400_BAD_REQUEST)
    
    logger.error(
        f"Domain Exception: {exc.error_code} | {exc.message} "
        f"on {request.method} {request.url.path}"
    )
    
    response = JSONResponse(
        status_code=status_code,
        content={
            "detail": exc.message,
            "error_code": exc.error_code,
        },
    )
    origin = request.headers.get("origin")
    if origin and settings.is_origin_allowed(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        if settings.CORS_ALLOW_CREDENTIALS:
            response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"

    return response


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled server errors (forces standard format & hides traceback)."""
    logger.critical(
        f"Unhandled System Exception: {str(exc)} "
        f"on {request.method} {request.url.path}",
        exc_info=True
    )
    
    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An unexpected internal server error occurred.",
            "error_code": "INTERNAL_SERVER_ERROR",
        },
    )
    origin = request.headers.get("origin")
    if origin and settings.is_origin_allowed(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        if settings.CORS_ALLOW_CREDENTIALS:
            response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"

    return response


# ── Static Uploads Mount ──────────────────────────────────────────────────────
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.UPLOAD_DIR / "evidence", exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(settings.UPLOAD_DIR)), name="uploads")


# ── Routing ───────────────────────────────────────────────────────────────────
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


# ── Root Welcome ──────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root_redirect() -> dict:
    """Return platform metadata on root query."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": f"{settings.API_V1_PREFIX}/docs"
    }
