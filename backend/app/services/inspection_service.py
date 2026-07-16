"""
Inspection service — business logic layer for inspection management.

Orchestrates inspection lifecycle:
- Creation (validates asset exists)
- Status transitions (PENDING → PROCESSING → COMPLETED / FAILED)
- Results population (called by the vision engine in Phase 2)
- Querying by asset or status
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.inspection import Inspection
from backend.app.repositories.asset_repository import AssetRepository
from backend.app.repositories.inspection_repository import InspectionRepository
from backend.app.schemas.common import PaginatedResponse
from backend.app.schemas.inspection import InspectionCreate, InspectionUpdate
from backend.app.services.base import BaseService

logger = logging.getLogger(__name__)


class InspectionService(BaseService):
    """
    Service layer for Inspection domain operations.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self._repo = InspectionRepository(session)
        self._asset_repo = AssetRepository(session)

    async def create_inspection(self, data: InspectionCreate) -> Inspection | None:
        """
        Create a new inspection record for an asset.

        Validates that the target asset exists before creating the record.

        Args:
            data: Validated InspectionCreate schema.

        Returns:
            Newly created Inspection, or None if the asset was not found.
        """
        if not await self._asset_repo.exists(data.asset_id):
            logger.warning(
                f"Cannot create inspection — asset not found: {data.asset_id!r}"
            )
            return None
        inspection = await self._repo.create(**data.model_dump())
        logger.info(
            f"Inspection created: id={inspection.id!r} asset={data.asset_id!r}"
        )
        return inspection

    async def get_inspection(self, inspection_id: str) -> Inspection | None:
        """Retrieve an inspection by ID. Returns None if not found."""
        return await self._repo.get_by_id(inspection_id)

    async def list_inspections(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[Inspection]:
        """Return a paginated list of all inspections, newest first."""
        items, total = await self._repo.get_all(
            page=page,
            page_size=page_size,
        )
        return PaginatedResponse.build(items, total, page, page_size)

    async def list_inspections_for_asset(self, asset_id: str) -> list[Inspection]:
        """Return all inspections for a specific asset (newest first)."""
        return await self._repo.get_by_asset(asset_id)

    async def update_inspection(
        self, inspection_id: str, data: InspectionUpdate
    ) -> Inspection | None:
        """
        Update inspection fields (PATCH semantics).

        Typically called by:
        - The vision engine to set status=PROCESSING and later COMPLETED
        - The API to record notes or correct error state

        Returns:
            Updated Inspection, or None if not found.
        """
        inspection = await self._repo.get_by_id(inspection_id)
        if inspection is None:
            logger.warning(f"Update failed — inspection not found: {inspection_id!r}")
            return None
        updated = await self._repo.update_fields(
            inspection, **data.model_dump(exclude_none=True)
        )
        logger.info(
            f"Inspection updated: id={inspection_id!r} status={updated.status.value!r}"
        )
        return updated

    async def get_pending_inspections(self) -> list[Inspection]:
        """Return all PENDING inspections. Used by the job queue in Phase 2."""
        return await self._repo.get_pending()
