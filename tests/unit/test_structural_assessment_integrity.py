"""
Structural Assessment Result Integrity Regression Tests.

Validates:
1. Zero detections do NOT automatically produce a perfect 100/100 health score.
2. Unsupported/generic model classes (e.g. COCO) are identified and marked unverified.
3. Correct handling of inference failures (status='unavailable', health_score=None).
4. Pending/processing inspections return status='insufficient_data', health_score=None.
5. Validated defect detections produce deterministic scoring via noisy-OR deductions.
6. Detection output and consistency between detections, inspection status, and health scores.
"""
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.asset import AssetType
from backend.app.models.detection import DefectType
from backend.app.models.inspection import InspectionSource, InspectionStatus
from backend.app.repositories.detection_repository import DetectionRepository
from backend.app.repositories.health_record_repository import HealthRecordRepository
from backend.app.schemas.asset import AssetCreate
from backend.app.schemas.inspection import InspectionCreate
from backend.app.services.asset_service import AssetService
from backend.app.services.inspection_service import InspectionService
from backend.app.services.structural_assessment_service import StructuralAssessmentService
from vision.detectors.base import IDetector, RawDetection
from vision.pipeline.cv_pipeline import CVInferencePipeline


class MockCOCODetector(IDetector):
    """Simulates a generic COCO model (unvalidated for structural defects)."""

    def __init__(self) -> None:
        self._name = "yolo11n-seg-coco.pt"
        self._device = "cpu"

    @property
    def model_name(self) -> str:
        return self._name

    @property
    def device(self) -> str:
        return self._device

    @property
    def is_defect_model(self) -> bool:
        return False

    @property
    def supported_defect_classes(self) -> list[str]:
        return []

    def predict(
        self, image: np.ndarray, confidence_threshold: float | None = None
    ) -> list[RawDetection]:
        # Generic COCO model detects 0 structural defects on a wall
        return []


class MockZeroDefectValidatedDetector(IDetector):
    """Simulates a validated crack detector that finds zero defects in a clean image."""

    def __init__(self) -> None:
        self._name = "yolo11n-crack-seg.pt"
        self._device = "cpu"

    @property
    def model_name(self) -> str:
        return self._name

    @property
    def device(self) -> str:
        return self._device

    @property
    def is_defect_model(self) -> bool:
        return True

    @property
    def supported_defect_classes(self) -> list[str]:
        return ["crack", "spalling"]

    def predict(
        self, image: np.ndarray, confidence_threshold: float | None = None
    ) -> list[RawDetection]:
        return []


class MockCrackValidatedDetector(IDetector):
    """Simulates a validated crack detector that finds an actual structural crack."""

    def __init__(self) -> None:
        self._name = "yolo11n-crack-seg.pt"
        self._device = "cpu"

    @property
    def model_name(self) -> str:
        return self._name

    @property
    def device(self) -> str:
        return self._device

    @property
    def is_defect_model(self) -> bool:
        return True

    @property
    def supported_defect_classes(self) -> list[str]:
        return ["crack", "spalling"]

    def predict(
        self, image: np.ndarray, confidence_threshold: float | None = None
    ) -> list[RawDetection]:
        mask = np.zeros((image.shape[0], image.shape[1]), dtype=np.uint8)
        mask[10:100, 10:20] = 1
        return [
            RawDetection(
                defect_type=DefectType.CRACK,
                confidence=0.92,
                bbox=[10.0, 10.0, 20.0, 100.0],
                mask=mask,
            )
        ]


@pytest.mark.asyncio
async def test_unsupported_model_classes_flagged(db_session: AsyncSession, tmp_path: Path):
    """An unvalidated model (e.g. COCO weights) must return status='unverified' without fake 100/100 score."""
    asset_svc = AssetService(db_session)
    insp_svc = InspectionService(db_session)
    assessment_svc = StructuralAssessmentService(db_session)

    test_img = tmp_path / "wall_crack.jpg"
    test_img.write_bytes(b"image bytes")

    asset = await asset_svc.create_asset(
        AssetCreate(name="Concrete Retaining Wall", asset_type=AssetType.BUILDING)
    )
    insp = await insp_svc.create_inspection(
        InspectionCreate(asset_id=asset.id, source=InspectionSource.IMAGE, input_path=str(test_img))
    )

    coco_detector = MockCOCODetector()
    pipeline = CVInferencePipeline(detector=coco_detector, slice_if_large=False)

    fake_rgb = np.zeros((640, 640, 3), dtype=np.uint8)
    with patch("vision.preprocessing.loader.ImageLoader.load_image", return_value=fake_rgb):
        completed_insp = await insp_svc.run_inspection(insp.id, pipeline=pipeline)

    assert completed_insp is not None
    assert completed_insp.status == InspectionStatus.COMPLETED
    assert completed_insp.defect_count == 0
    # Must NOT have a fake 100.0 health score!
    assert completed_insp.health_score is None

    # Assessment endpoint must report unverified status and disclose model limitations
    assessment = await assessment_svc.assess_inspection(
        insp.id, force_reassess=True, detector=coco_detector
    )
    assert assessment is not None
    assert assessment.status == "unverified"
    assert assessment.health_score is None
    assert assessment.risk_level is None
    assert assessment.model_validated is False
    assert any("not trained on structural defects" in lim.lower() for lim in assessment.limitations)
    assert any("fine-tuned structural defect detection model" in mi.lower() for mi in assessment.missing_inputs)


@pytest.mark.asyncio
async def test_zero_detections_does_not_produce_perfect_health_score(
    db_session: AsyncSession, tmp_path: Path
):
    """When a validated model finds 0 defects in a 2D image, health score must be unverified, NOT 100/100."""
    asset_svc = AssetService(db_session)
    insp_svc = InspectionService(db_session)
    assessment_svc = StructuralAssessmentService(db_session)

    test_img = tmp_path / "clean_wall.jpg"
    test_img.write_bytes(b"image bytes")

    asset = await asset_svc.create_asset(
        AssetCreate(name="Bridge Abutment East", asset_type=AssetType.BRIDGE)
    )
    insp = await insp_svc.create_inspection(
        InspectionCreate(asset_id=asset.id, source=InspectionSource.IMAGE, input_path=str(test_img))
    )

    val_detector = MockZeroDefectValidatedDetector()
    pipeline = CVInferencePipeline(detector=val_detector, slice_if_large=False)

    fake_rgb = np.zeros((640, 640, 3), dtype=np.uint8)
    with patch("vision.preprocessing.loader.ImageLoader.load_image", return_value=fake_rgb):
        completed_insp = await insp_svc.run_inspection(insp.id, pipeline=pipeline)

    assert completed_insp is not None
    assert completed_insp.status == InspectionStatus.COMPLETED
    assert completed_insp.defect_count == 0
    # Must NOT automatically be certified as 100/100 pristine!
    assert completed_insp.health_score is None

    # Check assessment response
    assessment = await assessment_svc.assess_inspection(
        insp.id, force_reassess=True, detector=val_detector
    )
    assert assessment is not None
    assert assessment.status == "unverified"
    assert assessment.health_score is None
    assert assessment.risk_level is None
    assert assessment.model_validated is True
    assert assessment.detected_defect_count == 0
    assert any("Zero visual surface defects were detected" in lim for lim in assessment.limitations)


@pytest.mark.asyncio
async def test_defects_detected_computes_score_and_persists_record(
    db_session: AsyncSession, tmp_path: Path
):
    """When a validated model detects defects, calculate score using noisy-OR deductions and persist."""
    asset_svc = AssetService(db_session)
    insp_svc = InspectionService(db_session)
    health_repo = HealthRecordRepository(db_session)

    test_img = tmp_path / "cracked_girder.jpg"
    test_img.write_bytes(b"image bytes")

    asset = await asset_svc.create_asset(
        AssetCreate(name="Steel Girder Span 2", asset_type=AssetType.BRIDGE)
    )
    insp = await insp_svc.create_inspection(
        InspectionCreate(asset_id=asset.id, source=InspectionSource.IMAGE, input_path=str(test_img))
    )

    crack_detector = MockCrackValidatedDetector()
    pipeline = CVInferencePipeline(detector=crack_detector, slice_if_large=False)

    fake_rgb = np.zeros((640, 640, 3), dtype=np.uint8)
    with patch("vision.preprocessing.loader.ImageLoader.load_image", return_value=fake_rgb):
        completed_insp = await insp_svc.run_inspection(insp.id, pipeline=pipeline)

    assert completed_insp is not None
    assert completed_insp.status == InspectionStatus.COMPLETED
    assert completed_insp.defect_count == 1
    # Health score should be deducted below 100.0 due to the observed crack
    assert completed_insp.health_score is not None
    assert 0.0 < completed_insp.health_score < 100.0

    # Ensure HealthRecord was persisted with severity breakdown
    records = await health_repo.get_by_inspection(insp.id)
    assert len(records) >= 1
    hr = records[0]
    assert hr.health_score == completed_insp.health_score
    assert "crack" in hr.severity_details


@pytest.mark.asyncio
async def test_inference_failure_handling(db_session: AsyncSession):
    """Inference failure returns status='unavailable' with health_score=None."""
    asset_svc = AssetService(db_session)
    insp_svc = InspectionService(db_session)
    assessment_svc = StructuralAssessmentService(db_session)

    asset = await asset_svc.create_asset(
        AssetCreate(name="Pier Substructure", asset_type=AssetType.BRIDGE)
    )
    insp = await insp_svc.create_inspection(
        InspectionCreate(asset_id=asset.id, source=InspectionSource.IMAGE)
    )
    await insp_svc._repo.update_fields(
        insp, status=InspectionStatus.FAILED, error_message="Out of memory during inference"
    )

    assessment = await assessment_svc.assess_inspection(insp.id)
    assert assessment is not None
    assert assessment.status == "unavailable"
    assert assessment.health_score is None
    assert assessment.risk_level is None
    assert "Out of memory during inference" in assessment.missing_inputs[0]


@pytest.mark.asyncio
async def test_pending_inspection_returns_insufficient_data(db_session: AsyncSession):
    """Pending inspection returns status='insufficient_data' with health_score=None."""
    asset_svc = AssetService(db_session)
    insp_svc = InspectionService(db_session)
    assessment_svc = StructuralAssessmentService(db_session)

    asset = await asset_svc.create_asset(
        AssetCreate(name="Deck Slab 1", asset_type=AssetType.BRIDGE)
    )
    insp = await insp_svc.create_inspection(
        InspectionCreate(asset_id=asset.id, source=InspectionSource.IMAGE)
    )

    assessment = await assessment_svc.assess_inspection(insp.id)
    assert assessment is not None
    assert assessment.status == "insufficient_data"
    assert assessment.health_score is None
    assert assessment.risk_level is None


@pytest.mark.asyncio
async def test_detection_output_and_status_consistency(db_session: AsyncSession, tmp_path: Path):
    """Verify consistency across defect count, detections rows, and assessment response."""
    asset_svc = AssetService(db_session)
    insp_svc = InspectionService(db_session)
    det_repo = DetectionRepository(db_session)
    assessment_svc = StructuralAssessmentService(db_session)

    test_img = tmp_path / "test_frame.jpg"
    test_img.write_bytes(b"image bytes")

    asset = await asset_svc.create_asset(
        AssetCreate(name="Tunnel Vault Section 4", asset_type=AssetType.TUNNEL)
    )
    insp = await insp_svc.create_inspection(
        InspectionCreate(asset_id=asset.id, source=InspectionSource.IMAGE, input_path=str(test_img))
    )

    detector = MockCrackValidatedDetector()
    pipeline = CVInferencePipeline(detector=detector, slice_if_large=False)

    fake_rgb = np.zeros((640, 640, 3), dtype=np.uint8)
    with patch("vision.preprocessing.loader.ImageLoader.load_image", return_value=fake_rgb):
        completed = await insp_svc.run_inspection(insp.id, pipeline=pipeline)

    assert completed is not None
    dets = await det_repo.get_by_inspection(completed.id)
    assert completed.defect_count == len(dets) == 1

    assessment = await assessment_svc.assess_inspection(
        completed.id, force_reassess=False, detector=detector
    )
    assert assessment is not None
    assert assessment.status == "completed"
    assert assessment.detected_defect_count == completed.defect_count == 1
    assert assessment.health_score == completed.health_score
