"""
FastAPI dependency providers.

Centralises all dependency injection wiring. Each provider function is
a FastAPI Depends() factory that constructs services/infrastructure per request.

Usage in endpoints::

    from backend.app.dependencies import AssetServiceDep

    @router.get("/")
    async def list_assets(service: AssetServiceDep) -> ...:
        ...
"""
import logging
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import Settings, get_settings
from backend.app.database.session import get_db
from backend.app.services.asset_service import AssetService
from backend.app.services.evidence_service import EvidenceService
from backend.app.services.inspection_service import InspectionService
from backend.app.services.structural_assessment_service import StructuralAssessmentService

logger = logging.getLogger(__name__)

# ── Infrastructure ────────────────────────────────────────────────────────────
DBSession = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


# ── Service factory functions ─────────────────────────────────────────────────
async def get_asset_service(session: DBSession) -> AssetService:
    """Provide an AssetService scoped to the current request."""
    return AssetService(session)


async def get_inspection_service(session: DBSession) -> InspectionService:
    """Provide an InspectionService scoped to the current request."""
    return InspectionService(session)


async def get_evidence_service(session: DBSession) -> EvidenceService:
    """Provide an EvidenceService scoped to the current request."""
    return EvidenceService(session)


async def get_structural_assessment_service(session: DBSession) -> StructuralAssessmentService:
    """Provide a StructuralAssessmentService scoped to the current request."""
    return StructuralAssessmentService(session)


# ── CV pipeline (Phase 2) ──────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def get_cv_pipeline() -> "CVInferencePipeline":  # noqa: F821 — forward ref, imported lazily below
    """
    Provide a process-wide singleton CVInferencePipeline.

    Loads the YOLO model into memory once and caches the instance for the
    lifetime of the process. If weights are not present on disk, instantiation
    will fail gracefully when first accessed.
    """
    settings = get_settings()

    # Lazy import to avoid loading heavy torch/cv2 libraries until needed
    from vision.pipeline.cv_pipeline import CVInferencePipeline
    from vision.detectors.yolo import YOLO11Detector

    logger.info(
        f"Initializing CVInferencePipeline singleton "
        f"(model={settings.DEFAULT_MODEL_NAME}, device={settings.INFERENCE_DEVICE})"
    )

    detector = YOLO11Detector(
        model_path=settings.default_model_path,
        device=settings.INFERENCE_DEVICE,
        default_conf=settings.CONFIDENCE_THRESHOLD,
        default_iou=settings.IOU_THRESHOLD,
    )

    return CVInferencePipeline(
        detector=detector,
        slice_height=settings.SLICE_HEIGHT,
        slice_width=settings.SLICE_WIDTH,
        slice_overlap_ratio=settings.SLICE_OVERLAP_RATIO,
    )


# ── Typed aliases (use these in endpoint signatures) ─────────────────────────
AssetServiceDep = Annotated[AssetService, Depends(get_asset_service)]
InspectionServiceDep = Annotated[InspectionService, Depends(get_inspection_service)]
EvidenceServiceDep = Annotated[EvidenceService, Depends(get_evidence_service)]
AssessmentServiceDep = Annotated[StructuralAssessmentService, Depends(get_structural_assessment_service)]
CVPipelineDep = Annotated["CVInferencePipeline", Depends(get_cv_pipeline)]  # noqa: F821
