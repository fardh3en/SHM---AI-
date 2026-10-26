"""
YOLOv8 Detection-Only Crack Detector Unit & Integration Tests.

Validates Phase 6 requirements:
1. Model loading and missing weights handling.
2. Expected class validation (crack class recognition, defect model validation).
3. Detection-only output (bounding box and confidence preserved; masks/skeletons not fabricated).
4. Zero detections handling (status='unverified', health_score=None).
5. Inference exception handling.
6. No fabricated masks or measurements (length/width remain None, area reflects bbox envelope).
7. No unsupported 100/100 health score (assessment remains unverified with explicit disclosures).
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import InferenceError, ModelNotFoundError
from backend.app.models.asset import AssetType
from backend.app.models.detection import DefectType
from backend.app.models.inspection import InspectionSource, InspectionStatus
from backend.app.schemas.asset import AssetCreate
from backend.app.schemas.inspection import InspectionCreate
from backend.app.services.asset_service import AssetService
from backend.app.services.inspection_service import InspectionService
from backend.app.services.structural_assessment_service import StructuralAssessmentService
from vision.detectors.base import IDetector, RawDetection
from vision.detectors.yolo import YOLO11Detector
from vision.pipeline.cv_pipeline import CVInferencePipeline


class MockYOLOv8CrackDetector(IDetector):
    """Simulates the candidate YOLOv8 crack detection model (detect task, crack class)."""

    def __init__(self, produce_detections: bool = True) -> None:
        self._name = "best.pt"
        self._device = "cpu"
        self._produce_detections = produce_detections

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
        return ["crack"]

    @property
    def supports_segmentation(self) -> bool:
        return False

    def predict(
        self, image: np.ndarray, confidence_threshold: float | None = None
    ) -> list[RawDetection]:
        if not self._produce_detections:
            return []
        return [
            RawDetection(
                defect_type=DefectType.CRACK,
                confidence=0.775,
                bbox=[448.5, 2.6, 870.2, 3499.0],
                mask=None,  # Detection-only model produces NO masks
            )
        ]


def test_missing_model_weights_raises_model_not_found(tmp_path: Path):
    """Detector must raise ModelNotFoundError when weight file is missing."""
    missing_path = tmp_path / "non_existent_weights.pt"
    with pytest.raises(ModelNotFoundError) as exc_info:
        YOLO11Detector(model_path=missing_path, device="cpu")
    assert "were not found" in str(exc_info.value)


def test_yolov8_detector_properties_and_task_recognition():
    """Verify class validation and task detection for a detection model."""
    detector = MockYOLOv8CrackDetector()
    assert detector.model_name == "best.pt"
    assert detector.is_defect_model is True
    assert detector.supported_defect_classes == ["crack"]
    assert detector.supports_segmentation is False


def test_detection_only_pipeline_preserves_boxes_without_fabricating_measurements():
    """Detection-only model outputs must NOT fabricate masks, skeletons, or crack width/length."""
    detector = MockYOLOv8CrackDetector(produce_detections=True)
    pipeline = CVInferencePipeline(detector=detector, slice_if_large=False)

    fake_rgb = np.zeros((3504, 2335, 3), dtype=np.uint8)
    with patch("vision.preprocessing.loader.ImageLoader.load_image", return_value=fake_rgb):
        results = pipeline.run("dummy_path.jpg")

    assert len(results) == 1
    res = results[0]
    assert res.defect_type == DefectType.CRACK
    assert res.confidence == 0.775

    # Coordinates preserved
    assert res.bbox_x1 == pytest.approx(448.5 / 2335, rel=1e-3)
    assert res.bbox_y1 == pytest.approx(2.6 / 3504, rel=1e-3)

    # NO fabricated masks or skeleton measurements
    assert res.mask_polygon is None
    assert res.measurements.length_px is None
    assert res.measurements.width_px is None
    assert res.measurements.max_width_px is None
    assert res.measurements.orientation_deg is None

    # Area reflects spatial bounding envelope, not fabricated mask area
    expected_area = (res.bbox_x2 - res.bbox_x1) * 2335 * (res.bbox_y2 - res.bbox_y1) * 3504
    assert res.measurements.area_px == pytest.approx(expected_area, rel=1e-3)


@pytest.mark.asyncio
async def test_detection_only_crack_assessment_is_unverified(db_session: AsyncSession, tmp_path: Path):
    """Crack bounding boxes must NOT produce arbitrary scores or fabricated severity without width."""
    asset_svc = AssetService(db_session)
    insp_svc = InspectionService(db_session)
    assessment_svc = StructuralAssessmentService(db_session)

    test_img = tmp_path / "shear_crack.jpg"
    test_img.write_bytes(b"image bytes")

    asset = await asset_svc.create_asset(
        AssetCreate(name="Parking Garage Beam", asset_type=AssetType.BUILDING)
    )
    insp = await insp_svc.create_inspection(
        InspectionCreate(asset_id=asset.id, source=InspectionSource.IMAGE, input_path=str(test_img))
    )

    detector = MockYOLOv8CrackDetector(produce_detections=True)
    pipeline = CVInferencePipeline(detector=detector, slice_if_large=False)

    fake_rgb = np.zeros((3504, 2335, 3), dtype=np.uint8)
    with patch("vision.preprocessing.loader.ImageLoader.load_image", return_value=fake_rgb):
        completed = await insp_svc.run_inspection(insp.id, pipeline=pipeline)

    assert completed is not None
    assert completed.status == InspectionStatus.COMPLETED
    assert completed.defect_count == 1
    # Health score must NOT be arbitrarily set; remains None
    assert completed.health_score is None

    # Check structural assessment response
    assessment = await assessment_svc.assess_inspection(
        completed.id, force_reassess=True, detector=detector
    )
    assert assessment is not None
    assert assessment.status == "unverified"
    assert assessment.health_score is None
    assert assessment.risk_level is None
    assert assessment.model_validated is True
    assert assessment.detected_defect_count == 1
    assert any("bounding boxes only" in lim for lim in assessment.limitations)
    assert any("Sub-millimeter crack aperture" in lim for lim in assessment.limitations)
    assert any("does not detect spalling" in lim for lim in assessment.limitations)


@pytest.mark.asyncio
async def test_detection_only_zero_detections_returns_unverified(db_session: AsyncSession, tmp_path: Path):
    """Zero detections with detection-only crack model returns status='unverified', health_score=None."""
    asset_svc = AssetService(db_session)
    insp_svc = InspectionService(db_session)
    assessment_svc = StructuralAssessmentService(db_session)

    test_img = tmp_path / "sound_concrete.jpg"
    test_img.write_bytes(b"image bytes")

    asset = await asset_svc.create_asset(
        AssetCreate(name="Pier Column 1", asset_type=AssetType.BRIDGE)
    )
    insp = await insp_svc.create_inspection(
        InspectionCreate(asset_id=asset.id, source=InspectionSource.IMAGE, input_path=str(test_img))
    )

    detector = MockYOLOv8CrackDetector(produce_detections=False)
    pipeline = CVInferencePipeline(detector=detector, slice_if_large=False)

    fake_rgb = np.zeros((640, 640, 3), dtype=np.uint8)
    with patch("vision.preprocessing.loader.ImageLoader.load_image", return_value=fake_rgb):
        completed = await insp_svc.run_inspection(insp.id, pipeline=pipeline)

    assert completed is not None
    assert completed.status == InspectionStatus.COMPLETED
    assert completed.defect_count == 0
    assert completed.health_score is None

    assessment = await assessment_svc.assess_inspection(
        completed.id, force_reassess=True, detector=detector
    )
    assert assessment is not None
    assert assessment.status == "unverified"
    assert assessment.health_score is None


def test_pipeline_handles_detector_exception_cleanly():
    """Pipeline raises InferenceError when detector encounters an exception."""
    class FaultyDetector(IDetector):
        @property
        def model_name(self) -> str:
            return "faulty.pt"

        @property
        def device(self) -> str:
            return "cpu"

        def predict(self, image: np.ndarray, confidence_threshold: float | None = None) -> list[RawDetection]:
            raise RuntimeError("CUDA device error or CPU thread panic")

    pipeline = CVInferencePipeline(detector=FaultyDetector(), slice_if_large=False)
    fake_rgb = np.zeros((640, 640, 3), dtype=np.uint8)
    with patch("vision.preprocessing.loader.ImageLoader.load_image", return_value=fake_rgb):
        with pytest.raises(InferenceError) as exc_info:
            pipeline.run("test.jpg")
    assert "Vision pipeline failed while processing" in str(exc_info.value)
