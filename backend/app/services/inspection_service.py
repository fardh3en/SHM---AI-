"""
Inspection service — business logic layer for inspection management.

Orchestrates inspection lifecycle:
- Creation (validates asset exists)
- Status transitions (PENDING → PROCESSING → COMPLETED / FAILED)
- Results population (Phase 2 vision pipeline execution)
- Automated structural health assessment execution (Phase 3 & 6)
- Querying by asset or status
"""
import asyncio
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
    from backend.app.models.detection import Detection
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
        """
        return await self._repo.get_all(
            page=page,
            page_size=page_size,
        )

    async def list_inspections_for_asset(self, asset_id: str) -> list[Inspection]:
        """Return all inspections for a specific asset (newest first)."""
        return await self._repo.get_by_asset(asset_id)

    async def get_detections_for_inspection(self, inspection_id: str) -> list["Detection"]:
        """Return all Detection records belonging to a given inspection."""
        return await self._detection_repo.get_by_inspection(inspection_id)

    async def compare_inspections(
        self, asset_id: str, base_id: str, target_id: str
    ):
        """
        Compare two inspections belonging to the same asset.

        Enforces asset boundary integrity, computes defect set transitions,
        delta scores, and adds structural engineering comparability disclosures.
        """
        from backend.app.repositories.health_record_repository import HealthRecordRepository
        from backend.app.schemas.comparison import (
            InspectionComparisonResponse,
            InspectionComparisonSummary,
        )

        base_insp = await self._repo.get_by_id(base_id)
        target_insp = await self._repo.get_by_id(target_id)

        if base_insp is None or target_insp is None:
            raise ValidationError("Both base and target inspections must exist to perform comparison.")

        if base_insp.asset_id != asset_id or target_insp.asset_id != asset_id:
            raise ValidationError(
                f"Both inspections must belong to asset '{asset_id}'. "
                f"Base belongs to '{base_insp.asset_id}', Target belongs to '{target_insp.asset_id}'."
            )

        asset = await self._asset_repo.get_by_id(asset_id)
        if asset is None:
            raise ValidationError(f"Asset '{asset_id}' not found.")

        base_dets = await self._detection_repo.get_by_inspection(base_id)
        target_dets = await self._detection_repo.get_by_inspection(target_id)

        health_repo = HealthRecordRepository(self.session)
        base_record = await health_repo.get_latest_for_inspection(base_id)
        target_record = await health_repo.get_latest_for_inspection(target_id)

        base_types = {d.defect_type.value for d in base_dets}
        target_types = {d.defect_type.value for d in target_dets}

        common_types = sorted(base_types & target_types)
        newly_observed = sorted(target_types - base_types)
        absent_in_target = sorted(base_types - target_types)

        base_area = sum(d.area_px for d in base_dets if d.area_px is not None)
        target_area = sum(d.area_px for d in target_dets if d.area_px is not None)
        area_delta = round(target_area - base_area, 2) if (base_dets or target_dets) else None

        score_delta = None
        if base_insp.health_score is not None and target_insp.health_score is not None:
            score_delta = round(target_insp.health_score - base_insp.health_score, 2)

        if base_insp.status != InspectionStatus.COMPLETED or target_insp.status != InspectionStatus.COMPLETED:
            comparability = "incomparable"
        elif base_insp.input_path == target_insp.input_path:
            comparability = "comparable"
        else:
            comparability = "partially_comparable"

        disclosures = [
            "Newly observed defect categories in the target inspection may represent newly developed physical deterioration OR pre-existing defects uncaptured during previous photographic framing.",
            "Absence of a previously observed defect category in the target inspection does NOT prove that remedial structural repair occurred; viewing perspective, lighting, or coverage may vary.",
            "Pixel measurement deltas (area_px) are indicative only and assume consistent camera distance, framing, and optical resolution.",
            "Structural health score delta requires equivalent scoring models and assessment versions for engineering validity.",
        ]

        base_summary = InspectionComparisonSummary(
            id=base_insp.id,
            created_at=base_insp.created_at.isoformat() if base_insp.created_at else "",
            source=base_insp.source.value,
            status=base_insp.status.value,
            defect_count=base_insp.defect_count,
            health_score=base_insp.health_score,
            assessment_method=base_record.assessment_method if base_record else None,
            input_path=base_insp.input_path,
            defect_types=sorted(base_types),
            total_area_px=round(base_area, 2) if base_dets else None,
        )

        target_summary = InspectionComparisonSummary(
            id=target_insp.id,
            created_at=target_insp.created_at.isoformat() if target_insp.created_at else "",
            source=target_insp.source.value,
            status=target_insp.status.value,
            defect_count=target_insp.defect_count,
            health_score=target_insp.health_score,
            assessment_method=target_record.assessment_method if target_record else None,
            input_path=target_insp.input_path,
            defect_types=sorted(target_types),
            total_area_px=round(target_area, 2) if target_dets else None,
        )

        return InspectionComparisonResponse(
            asset_id=asset.id,
            asset_name=asset.name,
            base_inspection=base_summary,
            target_inspection=target_summary,
            comparability_status=comparability,
            common_defect_types=common_types,
            newly_observed_defect_types=newly_observed,
            previously_observed_defect_types_absent=absent_in_target,
            health_score_delta=score_delta,
            defect_count_delta=target_insp.defect_count - base_insp.defect_count,
            measurement_comparison={
                "base_total_area_px": round(base_area, 2) if base_dets else None,
                "target_total_area_px": round(target_area, 2) if target_dets else None,
                "area_delta_px": area_delta,
                "comparability_caveat": (
                    "Identical media source" if comparability == "comparable"
                    else "Different media sources — metric comparison is uncalibrated"
                ),
            },
            disclosures_and_limitations=disclosures,
        )

    async def update_inspection(
        self, inspection_id: str, data: InspectionUpdate
    ) -> Inspection | None:
        """
        Update inspection fields (PATCH semantics).
        """
        inspection = await self._repo.get_by_id(inspection_id)
        if inspection is None:
            logger.warning(f"Update failed — inspection not found: {inspection_id!r}")
            return None

        update_data = data.model_dump(exclude_none=True)
        if "asset_id" in update_data:
            target_asset_id = update_data["asset_id"]
            if not await self._asset_repo.exists(target_asset_id):
                raise ValidationError(f"Target asset '{target_asset_id}' not found.")

        updated = await self._repo.update_fields(
            inspection, **update_data
        )
        logger.info(
            f"Inspection updated: id={inspection_id!r} status={updated.status.value!r}"
        )
        return updated

    async def get_pending_inspections(self) -> list[Inspection]:
        """Return all PENDING inspections. Used by the job queue."""
        return await self._repo.get_pending()

    @staticmethod
    def _resolve_input_path(input_path: str) -> Path:
        """Resolve a stored inspection input_path (web URI or filesystem path) to a disk Path."""
        settings = get_settings()
        if input_path.startswith(("http://", "https://")):
            from urllib.parse import urlparse
            input_path = urlparse(input_path).path

        p = Path(input_path)
        if p.is_file():
            return p
        clean = input_path.strip().lstrip("/")
        upload_resolved = settings.UPLOAD_DIR.resolve()
        base_resolved = settings.BASE_DIR.resolve()

        if clean.startswith("uploads/"):
            sub = clean[len("uploads/"):]
            candidate = (settings.UPLOAD_DIR / sub).resolve()
            if candidate.is_file() and candidate.is_relative_to(upload_resolved):
                return candidate
        candidate2 = (settings.UPLOAD_DIR / clean).resolve()
        if candidate2.is_file() and candidate2.is_relative_to(upload_resolved):
            return candidate2
        candidate3 = (settings.BASE_DIR / clean).resolve()
        if candidate3.is_file() and candidate3.is_relative_to(base_resolved):
            return candidate3
        return p

    async def run_inspection(
        self,
        inspection_id: str,
        pipeline: "IInferencePipeline | None" = None,
    ) -> Inspection | None:
        """
        Execute the computer vision pipeline for an inspection, synchronously,
        followed by automated structural health assessment and score persistence.
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

        evidence_size_kb = resolved_path.stat().st_size / 1024
        logger.info(
            f"[Stage 1: Evidence Verified] inspection_id={inspection_id!r} "
            f"file='{resolved_path.name}' size={evidence_size_kb:.1f}KB"
        )

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
                logger.info(
                    f"[Stage 2: Pipeline Resolved] inspection_id={inspection_id!r} "
                    f"detector={getattr(pipeline, '_detector', 'unknown')}"
                )
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
        logger.info(f"[Stage 3: Status Updated] Inspection marked as PROCESSING: id={inspection_id!r}")

        start_time = time.perf_counter()

        # Execute CPU-intensive computer vision pipeline in worker thread to prevent event loop starvation
        try:
            logger.info(
                f"[Stage 4: Vision Inference Dispatch] Offloading pipeline.run to thread worker for {resolved_path.name}..."
            )
            t_infer_start = time.perf_counter()
            detection_results = await asyncio.to_thread(pipeline.run, resolved_path)
            infer_ms = (time.perf_counter() - t_infer_start) * 1000
            logger.info(
                f"[Stage 4: Vision Inference Complete] id={inspection_id!r} in {infer_ms:.1f}ms: "
                f"{len(detection_results)} detection(s) found"
            )
            # Reclaim intermediate PyTorch and image memory buffers immediately
            import gc
            gc.collect()
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
            logger.exception(f"Unexpected error during vision pipeline execution: id={inspection_id!r}")
            return await self._repo.update_fields(
                inspection,
                status=InspectionStatus.FAILED,
                error_message=f"Vision pipeline processing error: {exc}",
                processing_time_ms=elapsed_ms,
            )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Execute persistence and structural assessment with safety wrapper
        try:
            # ── 5. Persist Detection rows ─────────────────────────────────────────
            if detection_results:
                t_persist = time.perf_counter()
                logger.info(
                    f"[Stage 5: Persisting Detections] Writing {len(detection_results)} detection(s) "
                    f"to database for inspection {inspection_id!r}..."
                )
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
                persist_ms = (time.perf_counter() - t_persist) * 1000
                logger.info(f"[Stage 5: Persist Complete] Saved in {persist_ms:.1f}ms for inspection {inspection_id!r}")

            # ── 6. Mark as completed ──────────────────────────────────────────────
            updated = await self._repo.update_fields(
                inspection,
                status=InspectionStatus.COMPLETED,
                defect_count=len(detection_results),
                processing_time_ms=elapsed_ms,
            )
            logger.info(f"[Stage 6: Status Completed] Inspection marked as COMPLETED: id={inspection_id!r}")

            # ── 7. Automated Structural Health Assessment ─────────────────────────
            try:
                t_assess = time.perf_counter()
                logger.info(f"[Stage 7: Structural Assessment] Calculating health score for {inspection_id!r}...")
                from backend.app.services.structural_assessment_service import (
                    StructuralAssessmentService,
                )
                assessment_svc = StructuralAssessmentService(self.session)
                await assessment_svc.assess_inspection(inspection_id, force_reassess=True)
                refreshed = await self._repo.get_by_id(inspection_id)
                if refreshed is not None:
                    updated = refreshed
                assess_ms = (time.perf_counter() - t_assess) * 1000
                logger.info(
                    f"[Stage 7: Structural Assessment Complete] Computed in {assess_ms:.1f}ms for {inspection_id!r}: "
                    f"health_score={updated.health_score}"
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    f"Automated health assessment failed for inspection {inspection_id!r}: {exc}",
                    exc_info=True,
                )

            total_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                f"[Pipeline Fully Finalized] id={inspection_id!r} "
                f"defects={len(detection_results)} total_time={total_ms:.1f}ms "
                f"health_score={updated.health_score}"
            )
            return updated
        except Exception as post_exc:  # noqa: BLE001
            total_elapsed_ms = (time.perf_counter() - start_time) * 1000
            err_msg = f"Database/assessment error during inspection finalization: {post_exc}"
            logger.error(f"Failed to finalize inspection {inspection_id!r}: {post_exc}", exc_info=True)
            return await self._repo.update_fields(
                inspection,
                status=InspectionStatus.FAILED,
                error_message=err_msg,
                processing_time_ms=total_elapsed_ms,
            )
