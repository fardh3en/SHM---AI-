"""
Detection repository — extends BaseRepository with detection-specific queries.
"""
from sqlalchemy import select

from backend.app.models.detection import Detection
from backend.app.repositories.base import BaseRepository


class DetectionRepository(BaseRepository[Detection]):
    """Data access layer for Detection records."""

    model = Detection

    async def get_by_inspection(self, inspection_id: str) -> list[Detection]:
        """Retrieve all detections belonging to a given inspection."""
        result = await self.session.execute(
            select(Detection).where(Detection.inspection_id == inspection_id)
        )
        return list(result.scalars().all())
