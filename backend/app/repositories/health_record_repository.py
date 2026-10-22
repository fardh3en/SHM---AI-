"""
HealthRecord repository — extends BaseRepository with health-record-specific queries.
"""
from sqlalchemy import select

from backend.app.models.health_record import HealthRecord
from backend.app.repositories.base import BaseRepository


class HealthRecordRepository(BaseRepository[HealthRecord]):
    """Data access layer for HealthRecord entities."""

    model = HealthRecord

    async def get_by_inspection(self, inspection_id: str) -> list[HealthRecord]:
        """Retrieve all health records for a given inspection, newest first."""
        result = await self.session.execute(
            select(HealthRecord)
            .where(HealthRecord.inspection_id == inspection_id)
            .order_by(HealthRecord.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_latest_for_inspection(self, inspection_id: str) -> HealthRecord | None:
        """Retrieve the most recent health record for a given inspection."""
        result = await self.session.execute(
            select(HealthRecord)
            .where(HealthRecord.inspection_id == inspection_id)
            .order_by(HealthRecord.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
