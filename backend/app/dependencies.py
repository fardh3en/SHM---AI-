"""
FastAPI dependency providers.

Centralises all dependency injection wiring. Each provider function is
a FastAPI Depends() factory that constructs services/infrastructure per request.

Usage in endpoints::

    from backend.app.dependencies import AssetServiceDep

    @router.get("/")
    async def list_assets(service: AssetServiceDep) -> ...:
        ...
"""
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import Settings, get_settings
from backend.app.database.session import get_db
from backend.app.services.asset_service import AssetService
from backend.app.services.inspection_service import InspectionService

# ── Infrastructure ────────────────────────────────────────────────────────────
DBSession = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


# ── Service factory functions ─────────────────────────────────────────────────
async def get_asset_service(session: DBSession) -> AssetService:
    """Provide an AssetService scoped to the current request."""
    return AssetService(session)


async def get_inspection_service(session: DBSession) -> InspectionService:
    """Provide an InspectionService scoped to the current request."""
    return InspectionService(session)


# ── Typed aliases (use these in endpoint signatures) ─────────────────────────
AssetServiceDep = Annotated[AssetService, Depends(get_asset_service)]
InspectionServiceDep = Annotated[InspectionService, Depends(get_inspection_service)]
