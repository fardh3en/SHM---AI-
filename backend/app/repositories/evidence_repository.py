"""
Evidence repository — database access for AssetEvidence records.
"""
from sqlalchemy import select

from backend.app.models.asset_evidence import AssetEvidence
from backend.app.repositories.base import BaseRepository


class EvidenceRepository(BaseRepository[AssetEvidence]):
    """Data access layer for AssetEvidence records."""

    model = AssetEvidence

    async def list_for_asset(self, asset_id: str) -> list[AssetEvidence]:
        """Fetch all evidence photographs for an asset, oldest first."""
        result = await self.session.execute(
            select(AssetEvidence)
            .where(AssetEvidence.asset_id == asset_id)
            .order_by(AssetEvidence.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_by_asset_and_filename(
        self, asset_id: str, filename: str
    ) -> AssetEvidence | None:
        """Find an evidence record by asset and filename (for idempotent seeding)."""
        result = await self.session.execute(
            select(AssetEvidence).where(
                AssetEvidence.asset_id == asset_id,
                AssetEvidence.filename == filename,
            )
        )
        return result.scalar_one_or_none()
