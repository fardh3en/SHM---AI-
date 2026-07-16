"""
System health and platform info endpoints.

These endpoints are consumed by:
- Load balancers (health check probes)
- Monitoring systems (uptime, version tracking)
- DevOps dashboards
"""
import platform
import sys
from datetime import datetime, timezone

from fastapi import APIRouter

from backend.app.config import get_settings

router = APIRouter(prefix="/system", tags=["System"])
_settings = get_settings()


@router.get(
    "/health",
    summary="Health check",
    description=(
        "Lightweight liveness probe. "
        "Returns HTTP 200 with service status when the API is operational."
    ),
    response_description="Service health status.",
)
async def health_check() -> dict:
    """
    Liveness probe for load balancers and orchestration systems.
    Should always return 200 when the process is running.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "service": _settings.APP_NAME,
        "version": _settings.APP_VERSION,
        "environment": _settings.APP_ENV,
    }


@router.get(
    "/info",
    summary="Platform info",
    description="Returns runtime environment and configuration information.",
)
async def platform_info() -> dict:
    """Extended platform and version information."""
    return {
        "app_name": _settings.APP_NAME,
        "version": _settings.APP_VERSION,
        "python_version": sys.version,
        "platform": platform.system(),
        "platform_version": platform.version(),
        "environment": _settings.APP_ENV,
        "debug": _settings.DEBUG,
        "api_prefix": _settings.API_V1_PREFIX,
        "default_model": _settings.DEFAULT_MODEL_NAME,
        "inference_device": _settings.INFERENCE_DEVICE,
    }
