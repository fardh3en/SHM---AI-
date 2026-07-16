"""
API v1 main router.

All sub-routers (system, assets, inspections, …) are registered here.
Future phase routers (detections, health, degradation, recommendations)
will be added here when their phases are implemented.
"""
from fastapi import APIRouter

from backend.app.api.v1.endpoints import assets, inspections, system

api_router = APIRouter()

# ── Phase 1 endpoints ─────────────────────────────────────────────────────────
api_router.include_router(system.router)
api_router.include_router(assets.router)
api_router.include_router(inspections.router)

# ── Future phase endpoints (uncomment when implemented) ───────────────────────
# Phase 2: from backend.app.api.v1.endpoints import detections
#           api_router.include_router(detections.router)
# Phase 3: from backend.app.api.v1.endpoints import health
#           api_router.include_router(health.router)
# Phase 4: from backend.app.api.v1.endpoints import degradation
#           api_router.include_router(degradation.router)
# Phase 5: from backend.app.api.v1.endpoints import recommendations
#           api_router.include_router(recommendations.router)
