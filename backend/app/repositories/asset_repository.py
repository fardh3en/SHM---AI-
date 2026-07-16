"""
Asset repository — extends BaseRepository with asset-specific queries.
"""
from sqlalchemy import select

from backend.app.models.asset import Asset, AssetStatus
from backend.app.repositories.base import BaseRepository


class AssetRepository(BaseRepository[Asset]):
    """Data access layer for Asset records."""

    model = Asset

    async def get_by_name(self, name: str) -> Asset | None:
        """Find an asset by exact name match (case-sensitive)."""
        result = await self.session.execute(
            select(Asset).where(Asset.name == name)
        )
        return result.scalar_one_or_none()

    async def get_active(self) -> list[Asset]:
        """Retrieve all assets with ACTIVE status."""
        result = await self.session.execute(
            select(Asset).where(Asset.status == AssetStatus.ACTIVE)
        )
        return list(result.scalars().all())

    async def update_health_score(self, asset_id: str, score: float) -> Asset | None:
        """
        Update the denormalised health score on the asset row.
        Called by the intelligence engine (Phase 3) after each inspection.
        """
        asset = await self.get_by_id(asset_id)
        if asset is None:
            return None
        asset.latest_health_score = score
        self.session.add(asset)
        await self.session.flush()
        await self.session.refresh(asset)
        return asset
