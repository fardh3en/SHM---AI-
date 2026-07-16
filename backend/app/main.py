"""
FastAPI application factory.

Registers routers, middleware, exception handlers, and lifecycle hooks.
Configures automatic DB initialization in development environments.
"""
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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

    # Development auto-tables. (In production, use Alembic migrations instead)
    if not settings.is_production:
        # Ensure the data directory exists for SQLite
        if "sqlite" in settings.DATABASE_URL:
            import os
            os.makedirs(settings.BASE_DIR / "data", exist_ok=True)
            os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        
        await create_db_and_tables()

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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Exception Handlers ────────────────────────────────────────────────────────
@app.exception_handler(SHMBaseException)
async def shm_exception_handler(request: Request, exc: SHMBaseException) -> JSONResponse:
    """Map domain-specific exceptions to client-friendly JSON responses."""
    # Find HTTPStatus mapped class attribute, fall back to 400
    status_code = getattr(exc, "http_status", status.HTTP_400_BAD_REQUEST)
    
    logger.error(
        f"Domain Exception: {exc.error_code} | {exc.message} "
        f"on {request.method} {request.url.path}"
    )
    
    return JSONResponse(
        status_code=status_code,
        content={
            "detail": exc.message,
            "error_code": exc.error_code,
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled server errors (forces standard format & hides traceback)."""
    logger.critical(
        f"Unhandled System Exception: {str(exc)} "
        f"on {request.method} {request.url.path}",
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An unexpected internal server error occurred.",
            "error_code": "INTERNAL_SERVER_ERROR",
        },
    )


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
