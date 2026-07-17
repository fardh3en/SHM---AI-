"""
Inspection service — business logic layer for inspection management.

Orchestrates inspection lifecycle:
- Creation (validates asset exists)
- Status transitions (PENDING → PROCESSING → COMPLETED / FAILED)
- Results population (Phase 2 vision pipeline execution)
- Querying by asset or status
"""
import logging
import time
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import InferenceError, ValidationError
from backend.app.models.inspection import Inspection, InspectionStatus
from backend.app.repositories.asset_repository import AssetRepository
from backend.app.repositories.detection_repository import DetectionRepository
from backend.app.repositories.inspection_repository import InspectionRepository
from backend.app.schemas.inspection import InspectionCreate, InspectionUpdate
from backend.app.services.base import BaseService

if TYPE_CHECKING:
    from vision.pipeline.base import IInferencePipeline

logger = logging.getLogger(__name__)


class InspectionService(BaseService):
    """
    Service layer for Inspection domain operations.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self._repo = InspectionRepository(session)
        self._asset_repo = AssetRepository(session)
        self._detection_repo = DetectionRepository(session)

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
    ) -> tuple[list[Inspection], int]:
        """
        Return a paginated list of all inspections, newest first.

        Returns:
            Tuple of (Inspection ORM objects for the requested page, total record count).
            Callers (typically API endpoints) are responsible for wrapping this
            in a PaginatedResponse[ResponseSchema] using their own Pydantic schema.
        """
        return await self._repo.get_all(
            page=page,
            page_size=page_size,
        )

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

    async def run_inspection(
        self,
        inspection_id: str,
        pipeline: "IInferencePipeline",
    ) -> Inspection | None:
        """
        Execute the computer vision pipeline for an inspection, synchronously.

        Runs entirely within the current request (no background task queue —
        this is a deliberate Phase 2 scope decision; async workers are planned
        for a later phase). Transitions the inspection through
        PENDING/PROCESSING -> COMPLETED or FAILED, and persists one Detection
        row per defect found.

        Args:
            inspection_id: UUID of the inspection to process.
            pipeline: Vision inference pipeline (injected by the caller so this
                service stays decoupled from any concrete detector implementation).

        Returns:
            The updated Inspection with results populated, or None if the
            inspection does not exist.

        Raises:
            ValidationError: If the inspection has no input_path to process,
                or is already PROCESSING/COMPLETED (re-running is not allowed
                via this method — callers should create a new inspection).
        """
        inspection = await self._repo.get_by_id(inspection_id)
        if inspection is None:
            logger.warning(f"Run failed — inspection not found: {inspection_id!r}")
            return None

        if not inspection.input_path:
            raise ValidationError(
                f"Inspection '{inspection_id}' has no input_path set; "
                "nothing to process."
            )

        if inspection.status in (InspectionStatus.PROCESSING, InspectionStatus.COMPLETED):
            raise ValidationError(
                f"Inspection '{inspection_id}' is already "
                f"'{inspection.status.value}'. Create a new inspection to re-run."
            )

        # ── Mark as processing ────────────────────────────────────────────────
        inspection = await self._repo.update_fields(
            inspection, status=InspectionStatus.PROCESSING, error_message=None
        )
        logger.info(f"Inspection processing started: id={inspection_id!r}")

        start_time = time.perf_counter()

        try:
            detection_results = pipeline.run(inspection.input_path)
        except InferenceError as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Inspection processing failed: id={inspection_id!r} error={exc}")
            return await self._repo.update_fields(
                inspection,
                status=InspectionStatus.FAILED,
                error_message=str(exc),
                processing_time_ms=elapsed_ms,
            )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # ── Persist Detection rows ────────────────────────────────────────────
        if detection_results:
            records = [
                {
                    "inspection_id": inspection_id,
                    "defect_type": result.defect_type,
                    "confidence": result.confidence,
                    "bbox_x1": result.bbox_x1,
                    "bbox_y1": result.bbox_y1,
                    "bbox_x2": result.bbox_x2,
                    "bbox_y2": result.bbox_y2,
                    "tile_x": result.tile_x,
                    "tile_y": result.tile_y,
                    "source_image": inspection.input_path,
                    "area_px": result.measurements.area_px,
                    "length_px": result.measurements.length_px,
                    "width_px": result.measurements.width_px,
                    "orientation_deg": result.measurements.orientation_deg,
                    "mask_polygon": result.mask_polygon,
                }
                for result in detection_results
            ]
            await self._detection_repo.bulk_create(records)

        # ── Mark as completed ─────────────────────────────────────────────────
        updated = await self._repo.update_fields(
            inspection,
            status=InspectionStatus.COMPLETED,
            defect_count=len(detection_results),
            processing_time_ms=elapsed_ms,
        )
        logger.info(
            f"Inspection processing completed: id={inspection_id!r} "
            f"defects={len(detection_results)} time={elapsed_ms:.1f}ms"
        )
        return updated
