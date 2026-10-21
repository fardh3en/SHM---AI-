"""
API v1 main router.

All sub-routers (system, assets, inspections, evidence, …) are registered here.
"""
from fastapi import APIRouter

from backend.app.api.v1.endpoints import assets, evidence, inspections, reports, system

api_router = APIRouter()

# ── Endpoints ─────────────────────────────────────────────────────────────────
api_router.include_router(system.router)
api_router.include_router(assets.router)
api_router.include_router(inspections.router)
api_router.include_router(evidence.router)
api_router.include_router(reports.router)
