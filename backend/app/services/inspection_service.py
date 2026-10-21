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
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.core.exceptions import InferenceError, ModelNotFoundError, ValidationError
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

    async def get_detections(self, inspection_id: str):
        """Retrieve all defect detection instances for an inspection. Returns None if inspection not found."""
        insp = await self._repo.get_by_id(inspection_id)
        if insp is None:
            return None
        return await self._detection_repo.get_by_inspection(inspection_id)

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

    async def get_detections_for_inspection(self, inspection_id: str) -> list[Detection]:
        """Return all Detection records belonging to a given inspection."""
        return await self._detection_repo.get_by_inspection(inspection_id)

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

    @staticmethod
    def _resolve_input_path(input_path: str) -> Path:
        """Resolve a stored inspection input_path (web URI or filesystem path) to a disk Path."""
        settings = get_settings()
        p = Path(input_path)
        if p.is_file():
            return p
        clean = input_path.strip().lstrip("/")
        if clean.startswith("uploads/"):
            sub = clean[len("uploads/"):]
            candidate = (settings.UPLOAD_DIR / sub).resolve()
            if candidate.is_file():
                return candidate
        candidate2 = (settings.UPLOAD_DIR / clean).resolve()
        if candidate2.is_file():
            return candidate2
        candidate3 = (settings.BASE_DIR / clean).resolve()
        if candidate3.is_file():
            return candidate3
        return p

    async def run_inspection(
        self,
        inspection_id: str,
        pipeline: "IInferencePipeline | None" = None,
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
            ValidationError: If the inspection has no input_path or invalid status.
            ModelNotFoundError: If configured vision model weights are missing.
            InferenceError: If model inference fails.
        """
        inspection = await self._repo.get_by_id(inspection_id)
        if inspection is None:
            logger.warning(f"Run failed — inspection not found: {inspection_id!r}")
            return None

        # ── 1. Validate Evidence ──────────────────────────────────────────────
        if not inspection.input_path:
            msg = (
                f"Inspection '{inspection_id}' has no photographic evidence attached. "
                "Upload or select an inspection photograph before running vision inference."
            )
            logger.warning(f"Run aborted — missing evidence for inspection: {inspection_id!r}")
            await self._repo.update_fields(
                inspection,
                status=InspectionStatus.FAILED,
                error_message=msg,
            )
            raise ValidationError(msg)

        resolved_path = self._resolve_input_path(inspection.input_path)
        if not resolved_path.is_file():
            msg = (
                f"Inspection evidence file '{inspection.input_path}' was not found on the server filesystem. "
                "Upload a valid image before running vision analysis."
            )
            logger.warning(f"Run aborted — evidence file missing on disk: {resolved_path}")
            await self._repo.update_fields(
                inspection,
                status=InspectionStatus.FAILED,
                error_message=msg,
            )
            raise ValidationError(msg)

        if inspection.status in (InspectionStatus.PROCESSING, InspectionStatus.COMPLETED):
            raise ValidationError(
                f"Inspection '{inspection_id}' is already "
                f"'{inspection.status.value}'. Create a new inspection or reset status to re-run."
            )

        # ── 2. Resolve Pipeline ───────────────────────────────────────────────
        if pipeline is None:
            from backend.app.dependencies import get_cv_pipeline
            try:
                pipeline = get_cv_pipeline()
            except (ModelNotFoundError, InferenceError) as exc:
                logger.error(f"Vision model resolution failed for {inspection_id!r}: {exc}", exc_info=True)
                await self._repo.update_fields(
                    inspection,
                    status=InspectionStatus.FAILED,
                    error_message=exc.message if hasattr(exc, "message") else str(exc),
                )
                raise exc
            except Exception as exc:
                logger.exception(f"Unexpected error resolving CV pipeline for {inspection_id!r}")
                err_msg = f"Failed to initialize vision inference pipeline: {exc}"
                await self._repo.update_fields(
                    inspection,
                    status=InspectionStatus.FAILED,
                    error_message=err_msg,
                )
                raise InferenceError(err_msg) from exc

        # ── 3. Mark as processing ─────────────────────────────────────────────
        inspection = await self._repo.update_fields(
            inspection, status=InspectionStatus.PROCESSING, error_message=None
        )
        logger.info(f"Inspection processing started: id={inspection_id!r}")

        start_time = time.perf_counter()

        try:
            detection_results = pipeline.run(resolved_path)
        except (InferenceError, ModelNotFoundError) as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            err_msg = exc.message if hasattr(exc, "message") else str(exc)
            logger.error(f"Inspection processing failed: id={inspection_id!r} error={err_msg}", exc_info=True)
            return await self._repo.update_fields(
                inspection,
                status=InspectionStatus.FAILED,
                error_message=err_msg,
                processing_time_ms=elapsed_ms,
            )
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.exception(f"Unexpected error during inspection processing: id={inspection_id!r}")
            return await self._repo.update_fields(
                inspection,
                status=InspectionStatus.FAILED,
                error_message=f"Vision pipeline processing error: {exc}",
                processing_time_ms=elapsed_ms,
            )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # ── 4. Persist Detection rows ─────────────────────────────────────────
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

        # ── 5. Mark as completed ──────────────────────────────────────────────
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
