"""
Evidence service — business logic for AssetEvidence operations.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.asset_evidence import AssetEvidence
from backend.app.repositories.asset_repository import AssetRepository
from backend.app.repositories.evidence_repository import EvidenceRepository
from backend.app.schemas.asset_evidence import AssetEvidenceCreate
from backend.app.services.base import BaseService

logger = logging.getLogger(__name__)


class EvidenceService(BaseService):
    """Service layer for AssetEvidence operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self._repo = EvidenceRepository(session)
        self._asset_repo = AssetRepository(session)

    async def create_evidence(self, data: AssetEvidenceCreate) -> AssetEvidence | None:
        """Create a new evidence record for an asset. Returns None if asset doesn't exist."""
        asset = await self._asset_repo.get_by_id(data.asset_id)
        if asset is None:
            logger.warning(f"Cannot create evidence: Asset '{data.asset_id}' not found.")
            return None

        # Check for duplicate
        existing = await self._repo.get_by_asset_and_filename(data.asset_id, data.filename)
        if existing:
            logger.info(f"Evidence {data.filename} already exists for asset {data.asset_id}.")
            return existing

        evidence = await self._repo.create(**data.model_dump(exclude_none=False))
        logger.info(f"Evidence created: id={evidence.id!r} filename={evidence.filename!r}")
        return evidence

    async def list_for_asset(self, asset_id: str) -> list[AssetEvidence]:
        """List all visual evidence items for a given asset."""
        return await self._repo.list_for_asset(asset_id)

    async def get_evidence(self, evidence_id: str) -> AssetEvidence | None:
        """Retrieve single evidence record by ID."""
        return await self._repo.get_by_id(evidence_id)
