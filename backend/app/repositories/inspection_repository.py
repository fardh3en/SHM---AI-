"""
Inspection repository — extends BaseRepository with inspection-specific queries.
"""
from sqlalchemy import select

from backend.app.models.inspection import Inspection, InspectionStatus
from backend.app.repositories.base import BaseRepository


class InspectionRepository(BaseRepository[Inspection]):
    """Data access layer for Inspection records."""

    model = Inspection

    async def get_by_asset(self, asset_id: str) -> list[Inspection]:
        """Retrieve all inspections for a given asset, newest first."""
        result = await self.session.execute(
            select(Inspection)
            .where(Inspection.asset_id == asset_id)
            .order_by(Inspection.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_pending(self) -> list[Inspection]:
        """Retrieve all inspections in PENDING state (queued for processing)."""
        result = await self.session.execute(
            select(Inspection).where(Inspection.status == InspectionStatus.PENDING)
        )
        return list(result.scalars().all())

    async def get_latest_for_asset(self, asset_id: str) -> Inspection | None:
        """Retrieve the most recent completed inspection for an asset."""
        result = await self.session.execute(
            select(Inspection)
            .where(
                Inspection.asset_id == asset_id,
                Inspection.status == InspectionStatus.COMPLETED,
            )
            .order_by(Inspection.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
