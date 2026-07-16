"""
Asset service — business logic layer for asset management.

Orchestrates asset CRUD operations, validates business rules,
and delegates all data access to the AssetRepository.

Responsibilities:
- Create, read, update, delete assets
- Validate uniqueness and business constraints
- Coordinate health score denormalisation after inspections (Phase 3)
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.asset import Asset
from backend.app.repositories.asset_repository import AssetRepository
from backend.app.schemas.asset import AssetCreate, AssetUpdate
from backend.app.schemas.common import PaginatedResponse
from backend.app.services.base import BaseService

logger = logging.getLogger(__name__)


class AssetService(BaseService):
    """
    Service layer for Asset domain operations.

    Injected into API endpoints via FastAPI's Depends() mechanism.
    Never imported directly by endpoint code — always accessed through DI.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self._repo = AssetRepository(session)

    async def create_asset(self, data: AssetCreate) -> Asset:
        """
        Create a new structural asset.

        Args:
            data: Validated AssetCreate schema.

        Returns:
            Persisted Asset ORM instance.
        """
        logger.info(f"Creating asset: name={data.name!r} type={data.asset_type.value!r}")
        asset = await self._repo.create(**data.model_dump(exclude_none=False))
        logger.info(f"Asset created: id={asset.id!r}")
        return asset

    async def get_asset(self, asset_id: str) -> Asset | None:
        """Retrieve an asset by ID. Returns None if not found."""
        return await self._repo.get_by_id(asset_id)

    async def list_assets(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[Asset]:
        """
        Return a paginated list of all assets.

        Args:
            page: 1-indexed page number.
            page_size: Results per page (max 100).

        Returns:
            PaginatedResponse wrapping a list of Asset ORM objects.
        """
        items, total = await self._repo.get_all(page=page, page_size=page_size)
        return PaginatedResponse.build(items, total, page, page_size)

    async def update_asset(self, asset_id: str, data: AssetUpdate) -> Asset | None:
        """
        Partially update an asset's fields.

        Args:
            asset_id: UUID of the asset to update.
            data: AssetUpdate schema — only non-None fields are applied.

        Returns:
            Updated Asset, or None if not found.
        """
        asset = await self._repo.get_by_id(asset_id)
        if asset is None:
            logger.warning(f"Update failed — asset not found: {asset_id!r}")
            return None
        updated = await self._repo.update(asset, **data.model_dump(exclude_none=True))
        logger.info(f"Asset updated: id={asset_id!r}")
        return updated

    async def delete_asset(self, asset_id: str) -> bool:
        """
        Permanently delete an asset and all linked records (cascade).

        Returns:
            True if deleted, False if the asset was not found.
        """
        asset = await self._repo.get_by_id(asset_id)
        if asset is None:
            return False
        await self._repo.delete(asset)
        logger.info(f"Asset deleted: id={asset_id!r}")
        return True

    async def record_health_score(self, asset_id: str, score: float) -> Asset | None:
        """
        Update the denormalised health score on the asset.

        Called by the intelligence engine (Phase 3) after completing an inspection.
        Keeps the asset's latest_health_score in sync for fast dashboard queries.
        """
        logger.debug(f"Updating health score: asset={asset_id!r} score={score:.1f}")
        return await self._repo.update_health_score(asset_id, score)
